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
    assert "studio-layout" in html
    assert "studio-edit" in html
    assert "applyLayout" in html


def test_a_dragged_place_is_written_into_the_page(tmp_path):
    placed, total = place_beats([_beat("b1", 3.0)])
    placed[0]["layout"] = {"pieces": {"title": {"x": -18.5, "y": 4.0}}}
    placed[0]["text"] = "Welcome."
    path = write_lesson_page("welcome", placed, total, tmp_path)
    html = path.read_text()
    saved = json.loads((tmp_path / "lesson.json").read_text())

    assert saved["beats"][0]["layout"] == {"pieces": {"title": {"x": -18.5, "y": 4.0}}}
    assert '"x": -18.5' in html
    assert "data-drag" in html
    assert path.read_text() == html


def test_rewrite_leaves_a_new_line_off_the_page_until_it_is_spoken(tmp_path):
    from app.lesson.page import rewrite_lesson_page

    placed, total = place_beats([_beat("b1", 3.0)])
    placed[0]["text"] = "Welcome."
    placed[0]["audio_file"] = "b1.mp3"
    path = write_lesson_page("welcome", placed, total, tmp_path)

    rewrite_lesson_page(
        str(path),
        [
            placed[0],
            {"id": "b2", "text": "Park is a place.", "visual": "A park.", "kind": "wording"},
        ],
    )

    saved = json.loads((tmp_path / "lesson.json").read_text())
    assert [beat["id"] for beat in saved["beats"]] == ["b1"]
    assert "Park is a place." not in path.read_text()


def test_rewrite_keeps_picture_settings_when_the_database_omits_them(tmp_path):
    from app.lesson.page import rewrite_lesson_page

    placed, total = place_beats([_beat("b1", 3.0)])
    placed[0]["text"] = "Welcome."
    placed[0]["settings"] = {"subject": "house", "title": "English Adventure", "labels": ["Welcome"]}
    placed[0]["component"] = "shape-picture"
    path = write_lesson_page("welcome", placed, total, tmp_path)
    (tmp_path / "b1.html").write_text(
        'const plan = {"id": "b1", "component": "shape-picture", '
        '"settings": {"subject": "house", "title": "English Adventure", "labels": ["Welcome"]}};\n'
    )

    rewrite_lesson_page(
        str(path),
        [{"id": "b1", "text": "Welcome.", "component": "shape-picture", "layout": {"pieces": {"title": {"x": -12, "y": 0}}}}],
    )

    saved = json.loads((tmp_path / "lesson.json").read_text())
    assert saved["beats"][0]["settings"]["title"] == "English Adventure"
    assert saved["beats"][0]["layout"] == {"pieces": {"title": {"x": -12, "y": 0}}}


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


def _house_visual(beat_id: str):
    from app.visuals.components import CHOICE_ADAPTER, end_state_for
    from app.visuals.generate import resolve_choice
    from app.visuals.schema import VisualBeat

    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "shape-picture",
            "settings": {"subject": "house", "title": "A house", "labels": ["roof"]},
        }
    )
    beat = VisualBeat(id=beat_id, text="A house has a roof.", visual="Draw a house.", duration=1.2)
    visual = resolve_choice(beat, choice)
    visual.html_file = ""
    return visual


def test_a_finished_picture_is_not_drawn_again(monkeypatch, tmp_path):
    import asyncio

    from app.ai_client import AIError
    from app.lesson.build import build_lesson

    drawn = []

    async def fake_generate(beat, output_dir=None):
        drawn.append(beat.id)
        raise AIError("stop")

    monkeypatch.setattr("app.lesson.build.generate_visual", fake_generate)

    saved = []
    payload = {
        "id": "long-lesson",
        "beats": [
            {
                "id": "b1",
                "text": "A house has a roof.",
                "visual": "Draw a house.",
                "duration": 1.2,
                "component": "shape-picture",
                "settings": {"subject": "house", "title": "A house", "labels": ["roof"]},
            },
            {"id": "b2", "text": "A tree grows.", "visual": "Draw a tree.", "duration": 1.2},
        ],
    }

    try:
        asyncio.run(build_lesson(payload, tmp_path, on_progress=saved.append))
    except AIError:
        pass

    assert drawn == ["b2"]
    assert saved == []


def test_each_new_picture_is_saved_before_the_next_line(monkeypatch, tmp_path):
    import asyncio

    from app.ai_client import AIError
    from app.lesson.build import build_lesson

    async def fake_generate(beat, output_dir=None):
        if beat.id == "b2":
            raise AIError("rate limit")
        visual = _house_visual(beat.id)
        path = tmp_path / f"{beat.id}.html"
        path.write_text("<html></html>")
        visual.html_file = str(path)
        return visual

    monkeypatch.setattr("app.lesson.build.generate_visual", fake_generate)

    snapshots = []
    payload = {
        "id": "long-lesson",
        "beats": [
            {"id": "b1", "text": "A house has a roof.", "visual": "Draw a house.", "duration": 1.2},
            {"id": "b2", "text": "A tree grows.", "visual": "Draw a tree.", "duration": 1.2},
        ],
    }

    try:
        asyncio.run(build_lesson(payload, tmp_path, on_progress=lambda beats: snapshots.append([dict(b) for b in beats])))
    except AIError as exc:
        assert exc.message == "rate limit"

    assert snapshots[0][0]["component"] == "shape-picture"
    assert snapshots[0][0]["id"] == "b1"
    assert not snapshots[0][1].get("component")


def test_audio_request_allows_one_hundred_lines():
    from app.schemas import LessonAudioRequest

    beats = [{"id": f"b{i}", "text": f"Line {i}."} for i in range(1, 101)]
    request = LessonAudioRequest(beats=beats)
    assert len(request.beats) == 100
