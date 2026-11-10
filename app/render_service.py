"""Draw each line and attach its spoken audio. The script queue does not do this."""

import logging
import shutil
import uuid
from pathlib import Path

from pydantic import ValidationError

from app.ai_client import AIError
from app.config import get_settings
from app.elevenlabs import ElevenLabsError
from app.lesson.build import build_lesson
from app.lesson_store import LessonRecord, LessonStore
from app.schemas import BeatIn, LessonAudioRequest
from app.script_queue import enqueue_render, is_last_attempt, uses_render_queue
from app.service import render_lesson_audio

logger = logging.getLogger(__name__)


class RenderFailed(Exception):
    def __init__(self, message: str, lesson_id: uuid.UUID) -> None:
        self.message = message
        self.lesson_id = lesson_id
        super().__init__(message)


async def write_render(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
    if uses_render_queue():
        enqueue_render(lesson.id)
        return lesson
    try:
        return await compose_lesson(store, lesson)
    except RenderFailed:
        store.mark_status(lesson.id, "render_failed")
        raise


async def run_queued_render(store: LessonStore, lesson_id: uuid.UUID, retry_count: int) -> tuple[int, dict]:
    lesson = store.get(lesson_id)
    if lesson is None or lesson.status != "rendering":
        status = "missing" if lesson is None else lesson.status
        logger.warning("queued render skipped lesson=%s status=%s retry=%s", lesson_id, status, retry_count)
        return 200, {"status": status}
    logger.info(
        "queued render start lesson=%s retry=%s beats=%s last=%s",
        lesson_id,
        retry_count,
        len(lesson.beats),
        is_last_attempt(retry_count),
    )
    try:
        saved = await compose_lesson(store, lesson)
    except RenderFailed as exc:
        logger.warning("queued render failed lesson=%s retry=%s: %s", lesson_id, retry_count, exc.message)
        if is_last_attempt(retry_count):
            store.mark_status(lesson_id, "render_failed")
            return 200, {"status": "render_failed", "error": exc.message}
        return 500, {"error": exc.message}
    except Exception:
        logger.exception("queued render crashed lesson=%s retry=%s", lesson_id, retry_count)
        message = "The lesson could not be made."
        if is_last_attempt(retry_count):
            store.mark_status(lesson_id, "render_failed")
            return 200, {"status": "render_failed", "error": message}
        return 500, {"error": message}
    logger.info("queued render done lesson=%s status=%s", saved.id, saved.status)
    return 200, {"status": saved.status, "id": str(saved.id)}


async def compose_lesson(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
    logger.info("compose audio start lesson=%s beats=%s", lesson.id, len(lesson.beats))
    try:
        audio = await render_lesson_audio(_audio_request(lesson))
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.get('loc', ()))}:{error.get('type')}"
            for error in exc.errors()[:8]
        )
        logger.warning("compose audio validation failed lesson=%s: %s", lesson.id, details or exc.__class__.__name__)
        raise RenderFailed("A line could not be spoken.", lesson.id) from exc
    except ElevenLabsError as exc:
        logger.warning(
            "compose audio failed lesson=%s beat=%s status=%s: %s",
            lesson.id,
            exc.beat_id or "-",
            exc.status_code,
            exc.message,
        )
        raise RenderFailed(exc.message, lesson.id) from exc

    directory = Path(get_settings().output_dir) / "lessons" / str(lesson.id)
    directory.mkdir(parents=True, exist_ok=True)
    spoken_by_id = {beat.id: beat for beat in audio.beats}
    payload = []
    for raw in lesson.beats:
        beat_id = str(raw.get("id"))
        timing = spoken_by_id.get(beat_id)
        if timing is None:
            raise RenderFailed("A spoken line is missing its audio.", lesson.id)
        name = Path(timing.audio_file).name
        try:
            shutil.copyfile(Path(audio.output_dir) / name, directory / name)
        except OSError as exc:
            raise RenderFailed("Could not save the spoken audio.", lesson.id) from exc
        payload.append(
            {
                **raw,
                "duration": timing.duration,
                "words": [word.model_dump() for word in timing.words],
                "audio_file": name,
            }
        )

    def persist_pictures(beats: list) -> None:
        store.save_beats(lesson.id, [dict(beat) for beat in beats])
        store.commit()

    logger.info("compose pictures start lesson=%s", lesson.id)
    try:
        built = await build_lesson(
            {"id": str(lesson.id), "beats": payload},
            directory,
            on_progress=persist_pictures,
        )
    except AIError as exc:
        logger.warning("compose pictures failed lesson=%s: %s", lesson.id, exc.message)
        raise RenderFailed(exc.message, lesson.id) from exc
    except ValidationError as exc:
        logger.warning("compose pictures invalid lesson=%s: %s", lesson.id, exc.__class__.__name__)
        raise RenderFailed("A picture could not be made for one line.", lesson.id) from exc

    pictures = {str(beat.get("id")): beat for beat in built.get("beats", [])}
    stored = []
    for raw in payload:
        picture = pictures.get(str(raw.get("id")), {})
        stored.append(
            {
                **raw,
                "component": picture.get("component") or raw.get("component") or "",
                "settings": raw.get("settings") or {},
                "start": picture.get("start"),
                "end": picture.get("end"),
                "pause_after": picture.get("pause_after"),
            }
        )
    saved = store.save_render(lesson.id, stored, str(directory), str(built["html_file"]))
    if saved is None:
        raise RenderFailed("Lesson not found", lesson.id)
    return saved


def _audio_request(lesson: LessonRecord) -> LessonAudioRequest:
    return LessonAudioRequest(
        beats=[
            BeatIn(
                id=str(beat.get("id")),
                text=str(beat.get("text") or ""),
                checkpoint=bool(beat.get("checkpoint")),
            )
            for beat in lesson.beats
        ]
    )
