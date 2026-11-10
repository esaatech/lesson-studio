"""Draw one line again. The other lines keep their pictures and their speech."""

import shutil
from pathlib import Path

from pydantic import ValidationError

from app.ai_client import AIError
from app.elevenlabs import ElevenLabsError
from app.lesson_store import LessonRecord, LessonStore
from app.schemas import BeatIn, LessonAudioRequest
from app.service import render_lesson_audio
from app.visuals.generate import generate_visual
from app.visuals.schema import VisualBeat, WordTime


class RedrawFailed(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


async def redraw_lesson_beat(
    store: LessonStore,
    lesson: LessonRecord,
    beat_id: str,
    text: str,
    visual: str,
    kind: str,
    checkpoint: bool,
) -> LessonRecord:
    beats = [dict(beat) for beat in lesson.beats]
    index = next((i for i, beat in enumerate(beats) if str(beat.get("id")) == beat_id), -1)
    if index < 0:
        raise RedrawFailed("Line not found")
    current = beats[index]
    spoken = text.strip()
    if spoken != str(current.get("text") or "").strip() or not _has_speech(current):
        current = await _speak_line(lesson, current, spoken, checkpoint)
    else:
        current = {
            **current,
            "text": spoken,
            "visual": visual.strip(),
            "kind": kind,
            "checkpoint": checkpoint,
        }
    current["visual"] = visual.strip()
    current["kind"] = kind
    current["checkpoint"] = checkpoint
    current.pop("layout", None)
    try:
        words = _word_times(current)
        picture = await generate_visual(
            VisualBeat(
                id=beat_id,
                text=spoken,
                visual=visual.strip(),
                kind=kind,
                checkpoint=checkpoint,
                duration=float(current.get("duration") or 0),
                words=words,
                audio_file=str(current.get("audio_file") or ""),
            ),
            Path(lesson.html_file).parent,
        )
    except ValidationError as exc:
        raise RedrawFailed("This picture could not be drawn.") from exc
    except AIError as exc:
        raise RedrawFailed(exc.message) from exc
    current["component"] = picture.component
    current["settings"] = picture.settings
    current["words"] = [word.model_dump() for word in picture.words] or current.get("words") or []
    current["layout"] = {}
    beats[index] = _place_line(beats, index, current)
    saved = store.save_beats(lesson.id, beats)
    if saved is None:
        raise RedrawFailed("Lesson not found")
    return saved


def _has_speech(beat: dict) -> bool:
    if not str(beat.get("audio_file") or "").strip():
        return False
    if float(beat.get("duration") or 0) <= 0:
        return False
    return bool(_word_times(beat))


def _word_times(beat: dict) -> list[WordTime]:
    words: list[WordTime] = []
    for raw in beat.get("words") or []:
        if not isinstance(raw, dict) or not str(raw.get("word") or "").strip():
            continue
        words.append(WordTime.model_validate(raw))
    return words


async def _speak_line(lesson: LessonRecord, beat: dict, text: str, checkpoint: bool) -> dict:
    try:
        audio = await render_lesson_audio(
            LessonAudioRequest(
                beats=[BeatIn(id=str(beat.get("id")), text=text, checkpoint=checkpoint)]
            )
        )
    except ValidationError as exc:
        raise RedrawFailed("This line could not be spoken.") from exc
    except ElevenLabsError as exc:
        raise RedrawFailed(exc.message) from exc
    item = audio.beats[0]
    name = Path(item.audio_file).name
    directory = Path(lesson.audio_dir) if lesson.audio_dir.strip() else Path(lesson.html_file).parent
    directory.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(Path(audio.output_dir) / name, directory / name)
    except OSError as exc:
        raise RedrawFailed("Could not save the spoken audio.") from exc
    return {
        **beat,
        "text": text,
        "duration": item.duration,
        "words": [word.model_dump() for word in item.words],
        "audio_file": name,
    }


def _place_line(beats: list[dict], index: int, beat: dict) -> dict:
    previous = beats[index - 1] if index else None
    had_speech = bool(str(beats[index].get("audio_file") or "").strip()) and float(beats[index].get("duration") or 0) > 0
    old_span = _span(beats[index]) if had_speech else 0.0
    new_duration = float(beat.get("duration") or 0)
    if had_speech:
        start = float(beats[index].get("start") or 0)
    elif previous is not None:
        start = float(previous.get("end") or 0)
    else:
        start = 0.0
    placed = {
        **beat,
        "start": round(start, 3),
        "end": round(start + new_duration, 3),
        "duration": new_duration,
        "pause_after": 0.0,
    }
    delta = round(new_duration - old_span, 3)
    if delta:
        for later in beats[index + 1 :]:
            later["start"] = round(float(later.get("start") or 0) + delta, 3)
            later["end"] = round(float(later.get("end") or 0) + delta, 3)
    return placed


def _span(beat: dict) -> float:
    duration = float(beat.get("duration") or 0)
    if duration <= 0:
        duration = max(0.0, float(beat.get("end") or 0) - float(beat.get("start") or 0))
    return duration + float(beat.get("pause_after") or 0)
