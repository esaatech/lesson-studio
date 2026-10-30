"""Place ready beats on one lesson clock. A question is spoken, then the next line starts."""

from app.visuals.schema import ResolvedVisual


def place_beats(beats: list[ResolvedVisual]) -> tuple[list[dict], float]:
    cursor = 0.0
    placed: list[dict] = []
    for beat in beats:
        duration = beat.duration or 0.0
        start = round(cursor, 3)
        end = round(start + duration, 3)
        record = beat.model_dump()
        record["start"] = start
        record["end"] = end
        record["pause_after"] = 0.0
        placed.append(record)
        cursor = end
    return placed, round(cursor, 3)
