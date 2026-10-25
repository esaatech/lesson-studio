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


def test_unknown_component_is_rejected():
    try:
        CHOICE_ADAPTER.validate_python({"component": "free-html", "settings": {}})
    except ValidationError:
        return
    raise AssertionError("expected an unknown component to be rejected")
