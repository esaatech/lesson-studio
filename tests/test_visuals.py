import json
from pathlib import Path

import pytest

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
    assert "label-plus-group" in instruction
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
    assert "play.hidden" not in html
    assert 'id="play"' in html
    assert (tmp_path / "visuals" / "s05-c.mp3").is_file()
    from app.visuals.render_html import html_with_inline_audio
    from app.visuals.schema import ResolvedVisual

    inlined = html_with_inline_audio(
        Path(page.html_file),
        ResolvedVisual(
            id="s05-c",
            component="digit-slide",
            settings={},
            end_state={},
            html_file=page.html_file,
            audio_file="s05-c.mp3",
        ),
    )
    assert "data:audio/mpeg;base64," in inlined


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


def test_visual_run_keeps_spoken_word_times(monkeypatch, tmp_path):
    from app.schemas import BeatOut, LessonAudioResponse, WordTiming
    from app.visuals.generate import resolve_choice
    from app.visuals.render_html import write_visual_page
    from app.visuals.schema import WordTime

    async def fake_audio(_request):
        return LessonAudioResponse(
            request_id="r1",
            output_dir=str(tmp_path),
            total_duration=0.4,
            beats=[
                BeatOut(
                    id="p1",
                    audio_file="p1.mp3",
                    start=0,
                    duration=0.4,
                    end=0.4,
                    words=[WordTiming(word="Hello", start=0.0, end=0.4)],
                )
            ],
        )

    async def fake_generate(beat, output_dir=None, task=None):
        assert all(isinstance(word, WordTime) for word in beat.words)
        choice = CHOICE_ADAPTER.validate_python(
            {"component": "kinetic-text", "settings": {"sentence": "Hello", "motion": "highlight"}}
        )
        visual = resolve_choice(beat, choice)
        page = write_visual_page(visual, tmp_path)
        visual.html_file = str(page)
        return visual

    monkeypatch.setattr("app.routes.render_lesson_audio", fake_audio)
    monkeypatch.setattr("app.routes.generate_visual", fake_generate)
    client = TestClient(app)
    response = client.post(
        "/v1/visuals",
        json={
            "id": "p1",
            "text": "Hello.",
            "visual": "Hello",
            "generate_audio": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["words"] == [{"word": "Hello", "start": 0.0, "end": 0.4}]


def test_visual_run_returns_html_and_uses_the_requested_prompt(monkeypatch, tmp_path):
    from app.runtime_settings import AITaskSettings
    from app.visuals.generate import resolve_choice
    from app.visuals.render_html import write_visual_page
    from app.visuals.schema import VisualBeat

    seen = {}

    async def fake_generate(beat, output_dir=None, task=None):
        seen["task"] = task
        seen["text"] = beat.text
        choice = CHOICE_ADAPTER.validate_python(
            {
                "component": "shape-picture",
                "settings": {"subject": "person", "title": "English Adventure", "labels": ["Welcome", "Explorers"]},
            }
        )
        visual = resolve_choice(beat, choice)
        page = write_visual_page(visual, tmp_path)
        visual.html_file = str(page)
        return visual

    monkeypatch.setattr("app.routes.generate_visual", fake_generate)
    client = TestClient(app)
    prompt = {
        "provider": "gemini",
        "model_id": "gemini-3.5-flash-lite",
        "temperature": 0.2,
        "system_prompt": "Choose a drawing. A person outline is allowed.",
    }
    response = client.post(
        "/v1/visuals",
        json={
            "id": "p1",
            "text": "Welcome, explorers, to our English Adventure where words come alive!",
            "visual": "A person outline titled English Adventure, labeled Welcome and Explorers.",
            "visual_generator": prompt,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["component"] == "shape-picture"
    assert body["settings"]["subject"] == "person"
    assert "English Adventure" in body["html"]
    assert "<div class=\"stage\"" in body["html"] or "id=\"stage\"" in body["html"]
    assert seen["task"] == AITaskSettings.model_validate(prompt)
    assert "Welcome" in seen["text"]


def test_drawn_pictures_are_offered_to_the_model():
    instruction = build_visual_instruction(VISUAL_GENERATOR_PROMPT)

    for name in ("label-plus-group", "compare-two", "path-trace", "part-whole", "cause-effect", "measure", "process-loop", "title-card", "kinetic-text", "code-line"):
        assert name in instruction
    assert "concept uses a relationship structure" in instruction
    assert "concept-scene" not in instruction
    assert "shape-picture" not in instruction


def test_catalog_for_a_kind_hides_the_other_tools():
    from app.visuals.components import component_catalog

    intro = component_catalog("intro")
    wording = component_catalog("wording")
    template = component_catalog("template")
    concept = component_catalog("concept")

    assert intro.startswith("This beat kind is intro.")
    assert "- title-card" in intro
    assert "- label-plus-group" not in intro
    assert "- kinetic-text" in wording
    assert "- title-card" not in wording
    assert "- label-plus-group" not in wording
    assert template == concept
    assert "- label-plus-group" in concept
    assert "- compare-two" in concept
    assert "- process-loop" in concept
    assert "- concept-scene" not in concept
    assert "- shape-picture" not in concept
    assert "- kinetic-text" not in concept


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


def test_title_card_and_kinetic_text_follow_spoken_words():
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="Welcome", start=0.1, end=0.4),
        WordTime(word="to", start=0.4, end=0.5),
        WordTime(word="English.", start=0.6, end=1.0),
    ]
    title = cues_for("title-card", {"title": "English", "subtitle": "", "emblem": "book"}, words, 2.0)
    assert title["reveal_0"] == 0.6
    kinetic = cues_for("kinetic-text", {"sentence": "Welcome to English", "motion": "highlight"}, words, 2.0)
    assert kinetic["reveal_0"] == 0.1
    assert kinetic["reveal_2"] == 0.6
    choice = CHOICE_ADAPTER.validate_python(
        {"component": "title-card", "settings": {"title": "English", "subtitle": "", "emblem": "book"}}
    )
    assert end_state_for(choice)["title"] == "English"


def test_wording_shows_on_screen_not_the_spoken_line(tmp_path):
    from app.visuals.generate import apply_on_screen_words, resolve_choice
    from app.visuals.schema import VisualBeat

    spoken = "Notice how each sentence begins with a capital and ends with a period."
    screen = "Max is my dog. He loves to run in the park. He always brings back his ball."
    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "kinetic-text",
            "settings": {"sentence": spoken, "motion": "reveal"},
        }
    )
    beat = VisualBeat(id="max1", text=spoken, visual=screen, kind="wording")
    fixed = apply_on_screen_words(beat, choice)
    assert fixed.settings.sentence == screen
    assert fixed.settings.motion == "highlight"
    visual = resolve_choice(beat, choice)
    html = write_visual_page(visual, tmp_path).read_text()
    assert visual.settings["sentence"] == screen
    assert "Max is my dog" in html
    assert "Notice how each sentence" not in html


def test_empty_on_screen_does_not_show_the_spoken_line(tmp_path):
    from app.visuals.generate import apply_on_screen_words, resolve_choice
    from app.visuals.schema import VisualBeat

    spoken = "Notice how each sentence begins with a capital and ends with a period."
    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "kinetic-text",
            "settings": {"sentence": spoken, "motion": "highlight"},
        }
    )
    beat = VisualBeat(id="blank1", text=spoken, visual="", kind="wording")
    fixed = apply_on_screen_words(beat, choice)
    assert fixed.settings.sentence == ""
    html = write_visual_page(resolve_choice(beat, choice), tmp_path).read_text()
    assert "Notice how each sentence" not in html


def test_a_label_plus_group_follows_spoken_cues(tmp_path):
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    words = [
        WordTime(word="A", start=0.0, end=0.1),
        WordTime(word="flock", start=0.2, end=0.5),
        WordTime(word="is", start=0.5, end=0.6),
        WordTime(word="one", start=0.6, end=0.8),
        WordTime(word="word", start=0.8, end=1.0),
        WordTime(word="for", start=1.0, end=1.1),
        WordTime(word="a", start=1.1, end=1.2),
        WordTime(word="whole", start=1.2, end=1.5),
        WordTime(word="group", start=1.5, end=1.8),
        WordTime(word="crowd", start=2.0, end=2.3),
        WordTime(word="herd", start=2.4, end=2.7),
        WordTime(word="bunch", start=2.8, end=3.1),
    ]
    settings = {
        "title": "collective noun",
        "badge": "1 word",
        "label": "flock",
        "group_icon": "bird",
        "count": 5,
        "caption": "whole group",
        "examples": [
            {"icon": "people", "label": "crowd"},
            {"icon": "paw", "label": "herd"},
            {"icon": "banana", "label": "bunch"},
        ],
    }
    cues = cues_for("label-plus-group", settings, words, 4.0)
    assert cues["reveal_0"] == 0.2
    assert cues["reveal_1"] == 1.2
    assert cues["reveal_2"] == 2.0
    choice = CHOICE_ADAPTER.validate_python({"component": "label-plus-group", "settings": settings})
    assert end_state_for(choice)["label"] == "flock"
    from app.visuals.generate import resolve_choice
    from app.visuals.render_html import write_visual_page
    from app.visuals.schema import VisualBeat

    visual = resolve_choice(
        VisualBeat(id="flock1", text="A flock is one word for a whole group.", visual="Flock stands for birds.", kind="concept"),
        choice,
    )
    html = write_visual_page(visual, tmp_path).read_text()
    assert 'viewBox="0 0 1000 562"' in html
    assert 'data-drag="label"' in html
    assert "flock" in html
    assert "ICON_PATHS" in html


def test_an_unknown_icon_is_rejected():
    try:
        CHOICE_ADAPTER.validate_python(
            {
                "component": "label-plus-group",
                "settings": {
                    "title": "group",
                    "label": "flock",
                    "group_icon": "dragon",
                    "count": 4,
                },
            }
        )
    except ValidationError:
        return
    raise AssertionError("expected an unknown icon to be rejected")


def test_unknown_component_is_rejected():
    try:
        CHOICE_ADAPTER.validate_python({"component": "free-html", "settings": {}})
    except ValidationError:
        return
    raise AssertionError("expected an unknown component to be rejected")


class ModelRateLimitError(Exception):
    pass


def test_picture_rate_limit_is_retried(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace

    from app.visuals import generate as generate_mod

    calls = {"n": 0}
    choice = CHOICE_ADAPTER.validate_python(
        {
            "component": "shape-picture",
            "settings": {"subject": "house", "title": "A house", "labels": ["roof"]},
        }
    )

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ModelRateLimitError("too many requests")
            return SimpleNamespace(output=choice)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(generate_mod, "Agent", FakeAgent)
    monkeypatch.setattr(generate_mod, "build_model", lambda _task: object())
    monkeypatch.setattr(generate_mod.asyncio, "sleep", no_sleep)

    beat = VisualBeat(id="b16", text="A house has a roof.", visual="Draw a house.")
    visual = asyncio.run(generate_mod.generate_visual(beat, tmp_path))

    assert calls["n"] == 2
    assert visual.component == "shape-picture"
    assert visual.id == "b16"


def test_a_wording_table_and_numbered_list_hold_at_most_five():
    from pydantic import TypeAdapter

    from app.runtime_settings import SCRIPT_DRAFTER_PROMPT
    from app.visuals.components import choice_type_for
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    wording = TypeAdapter(choice_type_for("wording"))
    table = {
        "component": "word-table",
        "settings": {
            "title": "Plurals",
            "headers": ["Word", "Plural", "Rule"],
            "rows": [
                ["hero", "heroes", "-es"],
                ["photo", "photos", "-s"],
                ["tomato", "tomatoes", "-es"],
                ["radio", "radios", "-s"],
                ["city", "cities", "-ies"],
            ],
        },
    }
    choice = wording.validate_python(table)
    assert choice.component == "word-table"
    assert len(choice.settings.rows) == 5

    too_many = {
        "component": "word-table",
        "settings": {
            "headers": ["Word", "Plural"],
            "rows": [["one", "ones"]] * 6,
        },
    }
    with pytest.raises(ValidationError):
        wording.validate_python(too_many)

    numbered = {
        "component": "numbered-list",
        "settings": {"items": ["heroes", "photos", "tomatoes", "radios", "cities"]},
    }
    assert wording.validate_python(numbered).component == "numbered-list"
    with pytest.raises(ValidationError):
        wording.validate_python({"component": "numbered-list", "settings": {"items": ["a", "b", "c", "d", "e", "f"]}})
    with pytest.raises(ValidationError):
        TypeAdapter(choice_type_for("concept")).validate_python(table)

    words = [
        WordTime(word="Heroes", start=0.4, end=0.9),
        WordTime(word="photos", start=1.5, end=2.0),
    ]
    cues = cues_for("word-table", table["settings"], words, 4)
    assert cues["reveal_0"] == 0.4
    assert cues["reveal_1"] == 1.5

    beat = VisualBeat(
        id="plurals",
        text="Heroes and photos.",
        visual="hero → heroes\nphoto → photos",
        duration=4,
        words=words,
    )
    visual = resolve_choice(beat, CHOICE_ADAPTER.validate_python(table))
    assert visual.component == "word-table"
    assert visual.end_state["rows"][0] == ["hero", "heroes", "-es"]

    crowded = VisualBeat(
        id="crowded",
        text="Here are the plurals.",
        visual="hero → heroes photo → photos tomato → tomatoes radio → radios city → cities box → boxes",
    )
    fallback = resolve_choice(crowded, CHOICE_ADAPTER.validate_python(numbered))
    assert fallback.component == "kinetic-text"
    assert "box → boxes" in fallback.settings["sentence"]

    assert "at most 5" in SCRIPT_DRAFTER_PROMPT
    assert "examples, questions, types, or other pieces of the same kind" in SCRIPT_DRAFTER_PROMPT
    assert "row" not in SCRIPT_DRAFTER_PROMPT.lower()
    assert "use word-table when they fall into columns" in VISUAL_GENERATOR_PROMPT
    assert "numbered-list when they are a short sequence" in VISUAL_GENERATOR_PROMPT
    assert "highlight-words is for that same single sentence" in VISUAL_GENERATOR_PROMPT


def test_picture_rate_limit_message_names_the_beat():
    from app.visuals.generate import _visual_error

    message = _visual_error(VisualBeat(id="b16", text="A house.", visual="Draw a house."), ModelRateLimitError())
    assert "b16" in message
    assert "rate-limited" in message.lower() or "Rate-limited" in message
