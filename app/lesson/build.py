"""Turn a beat list into one lesson page. Missing pictures are generated."""

from pathlib import Path

from app.runtime_settings import get_store
from app.visuals.generate import generate_visual, preview_visual
from app.visuals.schema import VisualBeat
from app.lesson.page import write_lesson_page
from app.lesson.timeline import place_beats


async def build_lesson(payload: dict, output_dir: Path | None = None) -> dict:
    lesson_id = str(payload.get("id") or "lesson")
    directory = output_dir or Path("output") / "lessons" / lesson_id
    pause = get_store().get().audio.checkpoint_pause_seconds
    resolved = []
    previous_end_state = None
    for raw in payload["beats"]:
        item = dict(raw)
        if previous_end_state is not None and not item.get("previous_end_state"):
            item["previous_end_state"] = previous_end_state
        if item.get("component") and item.get("settings"):
            visual = preview_visual(item, directory)
        else:
            visual = await generate_visual(VisualBeat.model_validate(item), directory)
        previous_end_state = visual.end_state
        resolved.append(visual)
    placed, total = place_beats(resolved, pause)
    spoken = {str(raw.get("id")): raw for raw in payload["beats"]}
    for beat in placed:
        raw = spoken.get(str(beat.get("id")), {})
        beat["text"] = str(raw.get("text") or beat.get("text") or "")
        if not beat.get("audio_file"):
            beat["audio_file"] = str(raw.get("audio_file") or "")
    page = write_lesson_page(lesson_id, placed, total, directory)
    return {
        "id": lesson_id,
        "html_file": str(page),
        "total_duration": total,
        "beats": [
            {
                "id": beat["id"],
                "component": beat["component"],
                "start": beat["start"],
                "end": beat["end"],
                "pause_after": beat["pause_after"],
            }
            for beat in placed
        ],
    }
