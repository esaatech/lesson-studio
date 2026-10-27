import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import get_settings
from app.main import app
from app.runtime_settings import VISUAL_GENERATOR_PROMPT, get_store, reset_store
from app.visuals.components import CHOICE_ADAPTER, component_catalog, end_state_for
from app.visuals.generate import resolve_choice
from app.visuals.instruction import build_visual_instruction
from app.visuals.render_html import write_visual_page
from app.visuals.schema import VisualBeat


def test_instruction_keeps_the_saved_rules_and_appends_the_catalog():
    instruction = build_visual_instruction(VISUAL_GENERATOR_PROMPT)

    assert "progress p" in instruction
    assert "digit-slide" in instruction
    assert "highlight-words" in instruction
    assert "label-callout" in instruction
    assert "path-trace" in instruction
    assert component_catalog() in instruction


def test_digit_slide_end_state_is_the_destination_column():
    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "digit-slide",
            "settings": {
                "digit": "5",
                "from_column": "ones",
                "to_column": "tenths",
                "label": "5 tenths = 0.5",
                "badge": "÷10",
            },
        }
    )
    beat = VisualBeat(
        id="s05-c",
        text="Move it one place right.",
        visual="The digit 5 slides into the tenths column.",
        duration=5.491,
    )

    visual = resolve_choice(beat, choice)

    assert visual.end_state["column"] == "tenths"
    assert visual.end_state["badge"] == "÷10"
    assert visual.duration == 5.491


def test_page_draws_from_progress_and_embeds_the_plan(tmp_path):
    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "digit-slide",
            "settings": {
                "digit": "5",
                "from_column": "ones",
                "to_column": "tenths",
                "label": "5 tenths = 0.5",
                "badge": "÷10",
            },
        }
    )
    beat = VisualBeat(id="s05-c", text="Move it.", visual="Slide the digit.")
    visual = resolve_choice(beat, choice)
    visual.html_file = "pending"

    path = write_visual_page(visual, tmp_path)
    html = path.read_text()

    assert "function frame(t)" in html
    assert "renderDigitSlide" in html
    assert "5 tenths = 0.5" in html
    plan = json.loads(html.split("const plan = ", 1)[1].split(";\n", 1)[0])
    assert plan["end_state"]["column"] == "tenths"
    assert end_state_for(choice)["digit"] == "5"


def test_pictures_appear_when_the_words_are_spoken():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="Inside", start=0.0, end=0.48),
        WordTime(word="the", start=0.48, end=0.61),
        WordTime(word="body,", start=0.61, end=1.11),
        WordTime(word="use", start=1.11, end=1.37),
        WordTime(word="semantic", start=1.37, end=1.86),
        WordTime(word="tags", start=1.86, end=2.22),
        WordTime(word="like", start=2.22, end=2.46),
        WordTime(word="header,", start=2.46, end=2.93),
        WordTime(word="nav,", start=2.93, end=3.32),
        WordTime(word="main,", start=3.32, end=3.56),
        WordTime(word="and", start=3.56, end=3.73),
        WordTime(word="footer", start=3.73, end=4.21),
    ]
    parts = [
        {"name": "header", "detail": ""},
        {"name": "nav", "detail": ""},
        {"name": "main", "detail": ""},
        {"name": "footer", "detail": ""},
    ]

    cues = cues_for("label-callout", {"parts": parts}, words, 7.813)

    assert cues["reveal_0"] == 2.46
    assert cues["reveal_1"] == 2.93
    assert cues["reveal_2"] == 3.32
    assert cues["reveal_3"] == 3.73


def test_highlight_uses_each_phrase_start_not_an_even_slice():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="Your", start=0.0, end=0.28),
        WordTime(word="turn:", start=0.28, end=1.22),
        WordTime(word="header,", start=2.57, end=3.01),
        WordTime(word="main", start=3.15, end=3.4),
        WordTime(word="section,", start=3.4, end=3.88),
        WordTime(word="footer,", start=4.13, end=5.03),
        WordTime(word="one", start=6.04, end=6.26),
        WordTime(word="class", start=6.26, end=6.64),
        WordTime(word="one", start=6.83, end=7.08),
        WordTime(word="Flexbox", start=7.08, end=7.75),
        WordTime(word="layout.", start=7.75, end=8.2),
    ]

    cues = cues_for(
        "highlight-words",
        {"emphasis": ["Your turn", "header", "main section", "footer", "one class", "one Flexbox layout"]},
        words,
        8.602,
    )

    assert cues["reveal_0"] == 0.0
    assert cues["reveal_1"] == 2.57
    assert cues["reveal_4"] == 6.04
    assert cues["reveal_5"] == 6.83


def test_a_card_that_is_not_spoken_waits_for_the_next_spoken_card():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="Today", start=0.0, end=0.43),
        WordTime(word="tools", start=1.18, end=1.62),
        WordTime(word="HTML", start=2.46, end=3.16),
        WordTime(word="CSS,", start=3.29, end=4.32),
    ]
    parts = [
        {"name": "VS Code installed", "detail": ""},
        {"name": "Browser dev tools open", "detail": ""},
        {"name": "HTML structure reviewed", "detail": ""},
        {"name": "CSS styling reviewed", "detail": ""},
    ]

    cues = cues_for("label-callout", {"parts": parts}, words, 7.488)

    assert cues["reveal_0"] == 1.18
    assert cues["reveal_1"] == 1.18
    assert cues["reveal_2"] == 2.46
    assert cues["reveal_3"] == 3.29


def test_path_steps_follow_the_spoken_words():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="Open", start=0.2, end=0.5),
        WordTime(word="the", start=0.5, end=0.7),
        WordTime(word="folder,", start=0.7, end=1.1),
        WordTime(word="then", start=1.4, end=1.7),
        WordTime(word="the", start=1.7, end=1.9),
        WordTime(word="file.", start=1.9, end=2.4),
    ]

    cues = cues_for("path-trace", {"steps": ["folder", "file"]}, words, 4.0)

    assert cues["reveal_0"] == 0.7
    assert cues["reveal_1"] == 1.9


def test_digit_slide_follows_the_spoken_words():
    from app.visuals.cues import digit_slide_cues
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="tenths,", start=1.892, end=2.368),
        WordTime(word="five", start=3.042, end=3.309),
        WordTime(word="tenths,", start=3.355, end=3.808),
    ]

    cues = digit_slide_cues("tenths", words, 5.491)

    assert cues["slide_end"] == 2.368
    assert cues["label_start"] == 3.042
    assert cues["label_end"] == 3.808
    assert cues["badge_start"] == 3.042


def test_preview_page_plays_the_beat_audio(tmp_path):
    from app.visuals.generate import preview_visual

    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"not-really-audio")
    page = preview_visual(
        {
            "id": "s05-c",
            "text": "Move it one place right, into the tenths.",
            "visual": "The digit slides into the tenths column.",
            "duration": 5.491,
            "audio_file": str(audio),
            "component": "digit-slide",
            "settings": {
                "digit": "5",
                "from_column": "ones",
                "to_column": "tenths",
                "label": "5 tenths = 0.5",
                "badge": "÷10",
            },
            "words": [
                {"word": "tenths,", "start": 1.892, "end": 2.368},
                {"word": "five", "start": 3.042, "end": 3.309},
                {"word": "tenths,", "start": 3.355, "end": 3.808},
            ],
        },
        tmp_path / "visuals",
    )

    html = Path(page.html_file).read_text()
    assert '"slide_end": 2.368' in html
    assert '"audio_file": "s05-c.mp3"' in html
    assert (tmp_path / "visuals" / "s05-c.mp3").is_file()


def test_missing_provider_key_is_a_message(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "AI_GEMINI_MODEL")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    reset_store()
    client = TestClient(app)

    response = client.post(
        "/v1/visuals",
        json={
            "id": "s05-c",
            "text": "Move it one place right.",
            "visual": "The digit 5 slides into the tenths column.",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": "GEMINI_API_KEY is not set"}


def test_drawn_pictures_are_offered_to_the_model():
    instruction = build_visual_instruction(VISUAL_GENERATOR_PROMPT)

    for name in ("stroke-diagram", "shape-picture", "arrow-link", "before-after", "code-line", "measure"):
        assert name in instruction
    assert "Prefer a drawn picture" in instruction


def test_a_drawn_picture_follows_the_spoken_words():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="The", start=0.0, end=0.2),
        WordTime(word="cat", start=0.3, end=0.6),
        WordTime(word="is", start=0.7, end=0.9),
        WordTime(word="on", start=1.1, end=1.4),
        WordTime(word="the", start=1.4, end=1.6),
        WordTime(word="box.", start=1.7, end=2.1),
    ]

    cues = cues_for("arrow-link", {"left": "cat", "relation": "on", "right": "box"}, words, 3.0)

    assert cues["reveal_0"] == 0.3
    assert cues["reveal_1"] == 1.1
    assert cues["reveal_2"] == 1.7

    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "shape-picture",
            "settings": {"subject": "house", "title": "A house", "labels": ["roof", "door"]},
        }
    )
    assert end_state_for(choice)["subject"] == "house"


def test_a_measure_caption_waits_until_it_is_spoken():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="zero", start=0.2, end=0.5),
        WordTime(word="five", start=1.2, end=1.6),
        WordTime(word="ten", start=2.2, end=2.6),
        WordTime(word="halfway", start=3.0, end=3.5),
    ]

    cues = cues_for(
        "measure",
        {"kind": "number-line", "marks": ["zero", "five", "ten"], "caption": "halfway"},
        words,
        4.0,
    )

    assert cues["reveal_0"] == 0.2
    assert cues["reveal_2"] == 2.2
    assert cues["reveal_3"] == 3.0


def test_unknown_component_is_rejected():
    try:
        CHOICE_ADAPTER.validate_python({"component": "free-html", "settings": {}})
    except ValidationError:
        return
    raise AssertionError("expected an unknown component to be rejected")
