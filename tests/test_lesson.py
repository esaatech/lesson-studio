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


def test_a_question_is_spoken_and_the_next_line_starts():
    placed, total = place_beats(
        [_beat("s05-a", 3.076), _beat("s05-c", 5.491), _beat("s05-question", 1.729, checkpoint=True)],
    )

    assert [(beat["id"], beat["start"], beat["end"], beat["pause_after"]) for beat in placed] == [
        ("s05-a", 0.0, 3.076, 0.0),
        ("s05-c", 3.076, 8.567, 0.0),
        ("s05-question", 8.567, 10.296, 0.0),
    ]
    assert placed[2]["checkpoint"] is True
    assert total == 10.296


def test_lesson_page_lists_every_beat(tmp_path):
    placed, total = place_beats(
        [_beat("s05-a", 3.076), _beat("s05-c", 5.491), _beat("s05-checkpoint", 1.729, checkpoint=True)],
    )

    path = write_lesson_page("slide-5", placed, total, tmp_path)
    html = path.read_text()

    assert path.name == "index.html"
    assert "s05-a" in html
    assert "s05-c" in html
    assert "s05-checkpoint" in html
    assert "10.296" in html
    assert '"pause_after": 0.0' in html
    assert "renderLessonFrame" in html
    assert 'get("capture")' in html
    saved = json.loads((tmp_path / "lesson.json").read_text())
    assert saved["total_duration"] == 10.296


def test_lesson_page_reveals_a_word_when_it_is_spoken(tmp_path):
    beat = _beat("b11", 8.602).model_dump()
    beat["settings"] = {
        "sentence": "Your turn: build a header.",
        "emphasis": ["Your turn", "header"],
    }
    beat["words"] = [
        {"word": "Your", "start": 0.0, "end": 0.28},
        {"word": "turn:", "start": 0.28, "end": 1.22},
        {"word": "header,", "start": 2.57, "end": 3.01},
    ]
    beat["start"] = 0.0
    beat["end"] = 8.602
    beat["pause_after"] = 0.0

    path = write_lesson_page("timing", [beat], 8.602, tmp_path)
    saved = json.loads((tmp_path / "lesson.json").read_text())

    assert saved["beats"][0]["cues"]["reveal_1"] == 2.57
    html = path.read_text()
    assert '"reveal_1": 2.57' in html
    assert "function escapeHtml" in html
    assert "function placeStage" in html
    assert "function renderShapePicture" in html
    assert "function renderArrowLink" in html
    assert "function renderCodeLine" in html
