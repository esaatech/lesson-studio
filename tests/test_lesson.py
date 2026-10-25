import json

from app.lesson.page import write_lesson_page
from app.lesson.timeline import place_beats
from app.visuals.schema import ResolvedVisual


def _beat(beat_id: str, duration: float, checkpoint: bool = False) -> ResolvedVisual:
    return ResolvedVisual(
        id=beat_id,
        component="highlight-words",
        settings={"sentence": beat_id, "emphasis": [beat_id]},
        end_state={"component": "highlight-words"},
        duration=duration,
        checkpoint=checkpoint,
        html_file="",
    )


def test_checkpoint_pause_is_part_of_the_lesson_clock():
    placed, total = place_beats(
        [_beat("s05-a", 3.076), _beat("s05-c", 5.491), _beat("s05-checkpoint", 1.729, checkpoint=True)],
        checkpoint_pause_seconds=2.0,
    )

    assert [(beat["id"], beat["start"], beat["end"], beat["pause_after"]) for beat in placed] == [
        ("s05-a", 0.0, 3.076, 0.0),
        ("s05-c", 3.076, 8.567, 0.0),
        ("s05-checkpoint", 8.567, 10.296, 2.0),
    ]
    assert total == 12.296


def test_lesson_page_lists_every_beat(tmp_path):
    placed, total = place_beats(
        [_beat("s05-a", 3.076), _beat("s05-c", 5.491), _beat("s05-checkpoint", 1.729, checkpoint=True)],
        checkpoint_pause_seconds=2.0,
    )

    path = write_lesson_page("slide-5", placed, total, tmp_path)
    html = path.read_text()

    assert path.name == "index.html"
    assert "s05-a" in html
    assert "s05-c" in html
    assert "s05-checkpoint" in html
    assert "12.296" in html
    assert '"pause_after": 2.0' in html
    assert "renderLessonFrame" in html
    assert 'get("capture")' in html
    saved = json.loads((tmp_path / "lesson.json").read_text())
    assert saved["total_duration"] == 12.296
