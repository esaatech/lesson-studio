"""Place ready beats on one lesson clock, including checkpoint pauses."""

from app.visuals.schema import ResolvedVisual


def place_beats(beats: list[ResolvedVisual], checkpoint_pause_seconds: float) -> tuple[list[dict], float]:
    cursor = 0.0
    placed: list[dict] = []
    for beat in beats:
        duration = beat.duration or 0.0
        pause = round(checkpoint_pause_seconds, 3) if beat.checkpoint else 0.0
        start = round(cursor, 3)
        end = round(start + duration, 3)
        record = beat.model_dump()
        record["start"] = start
        record["end"] = end
        record["pause_after"] = pause
        placed.append(record)
        cursor = end + pause
    return placed, round(cursor, 3)
