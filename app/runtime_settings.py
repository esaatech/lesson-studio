"""Defaults the service can run with, plus the file Django updates."""

import json
import secrets
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import Settings, get_settings

Provider = Literal["openai", "gemini", "deepseek"]
Renderer = Literal["html", "manim"]


class AudioSettings(BaseModel):
    voice_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    padding_seconds: float = Field(ge=0)
    checkpoint_pause_seconds: float = Field(ge=0)
    concurrency: int = Field(ge=1, le=4)


class AudioSettingsPatch(BaseModel):
    voice_id: str | None = Field(default=None, min_length=1, max_length=100)
    model_id: str | None = Field(default=None, min_length=1, max_length=100)
    padding_seconds: float | None = Field(default=None, ge=0)
    checkpoint_pause_seconds: float | None = Field(default=None, ge=0)
    concurrency: int | None = Field(default=None, ge=1, le=4)


class AITaskSettings(BaseModel):
    provider: Provider
    model_id: str = Field(min_length=1, max_length=100)
    temperature: float = Field(ge=0, le=2)
    system_prompt: str = Field(min_length=1, max_length=20000)


class RuntimeSettings(BaseModel):
    audio: AudioSettings
    script_drafter: AITaskSettings
    visual_generator: AITaskSettings
    renderer: Renderer = "html"


class SettingsPatch(BaseModel):
    """Sections present here replace the saved values. Omitted sections stay as they are."""

    audio: AudioSettingsPatch | None = None
    script_drafter: AITaskSettings | None = None
    visual_generator: AITaskSettings | None = None
    renderer: Renderer | None = None


SCRIPT_DRAFTER_PROMPT = """You draft a lesson as beats for a teacher.
Return JSON only. Each beat has id, text, kind, visual, and checkpoint.
text is one spoken sentence a teacher would say in one breath, at most 180 characters. One breath is one idea. A definition is one beat. An example is another beat.
When one beat would list several examples, questions, types, or other pieces of the same kind, put at most 5 in that beat. If there are more, split them so each beat still has at most 5, and give each beat its own spoken line.
kind is intro, wording, or concept. The job of the line, not a layout name.
intro names what is starting. The first beat may be one intro that names the whole lesson. When the source is divided into named sections, begin each section with its own intro that names that section, before any teaching in the section. visual is that name, optional subtitle, optional one emblem. Do not explain an idea on an intro.
wording is for when students should look at the language itself: a word, a sentence, an example paragraph, syllables, a line of code, a digit in place value. visual is the words they should see. It can be the example on the board while text is what the teacher says about it. Use wording when no diagram is needed.
concept is a relationship students should see: one word for a group, two things compared, steps in order, parts of a whole, cause and effect, a number line, or a cycle. visual names the relationship and the short labels. The same structure is used in English, math, and science. If no structure fits, use wording.
A welcome is intro. A sentence about the wording is wording. "A flock is one word for a group of birds" is concept.
When a thought is finished, you may add one sentence a teacher would say next: a short check with the class, or a flash question about what was just taught. Fit the age and the thought. That line keeps the same kind as the thought it follows, or wording if it repeats the words just taught.
checkpoint is true on a sentence that asks the student something.
Use the subject, grade, and objective you are given. Do not write HTML."""

VISUAL_GENERATOR_PROMPT = """You choose one component for one lesson beat.
Obey the beat kind. intro may only use title-card. wording may only use kinetic-text, highlight-words, numbered-list, word-table, digit-slide, or code-line. concept may only use a relationship structure from the catalog: label-plus-group, compare-two, path-trace, part-whole, cause-effect, measure, or process-loop.
Use the narration, the visual description, the duration, and the previous end state.
title-card is a large name, optional subtitle, optional one emblem. The opening intro names the lesson. A later intro names the section that is starting. It is not a diagram.
kinetic-text is for one wording sentence: students see the On screen text only. Put that text in sentence. If On screen is empty, sentence is empty and the board is blank. Never copy the spoken line onto the board. To show the spoken line, it must already be in On screen. highlight-words is for that same single sentence, and lights words that are both on screen and spoken. When On screen is several examples, questions, types, or other pieces of the same kind, and there are 5 or fewer, use word-table when they fall into columns, such as a word, its plural, and the rule, and numbered-list when they are a short sequence. If there are more than 5, use kinetic-text or highlight-words so nothing is left off the frame. digit-slide is only when one digit moves between place-value columns. code-line is one line of code.
You never write coordinates, SVG, HTML, CSS, or JavaScript. You pick a structure, labels, and icons from the allowed icon list. The renderer places everything.
label-plus-group is one word that stands for many things: a label, a ring of the same icon, optional other examples. compare-two is two things side by side. path-trace is steps on a line. part-whole is named parts of one whole. cause-effect is this leads to that. measure is a number line or a filling bar. process-loop is a cycle.
For concept, on-screen labels must be words that are actually spoken, so each part can appear on time. For wording, students see On screen only. Empty On screen is a blank board. The spoken line is never copied onto the board.
Labels are one or two words.
The picture must be a function of progress p, from 0 to 1. The same p always shows the same frame.
Return JSON only.
Do not invent an end state. The component records that when p is 1."""


def default_model_for(settings: Settings, provider: str) -> str:
    models = {
        "gemini": settings.ai_gemini_model,
        "deepseek": settings.ai_deepseek_model,
        "openai": settings.ai_openai_model,
    }
    return models.get(provider, settings.ai_gemini_model)


def defaults_from_env(settings: Settings) -> RuntimeSettings:
    provider = settings.resolved_ai_provider()
    model_id = default_model_for(settings, provider)
    return RuntimeSettings(
        audio=AudioSettings(
            voice_id=settings.eleven_voice_id,
            model_id=settings.eleven_model_id,
            padding_seconds=settings.beat_padding_seconds,
            checkpoint_pause_seconds=settings.checkpoint_pause_seconds,
            concurrency=settings.eleven_concurrency,
        ),
        script_drafter=AITaskSettings(
            provider=provider,
            model_id=model_id,
            temperature=0.4,
            system_prompt=SCRIPT_DRAFTER_PROMPT,
        ),
        visual_generator=AITaskSettings(
            provider=provider,
            model_id=model_id,
            temperature=0.2,
            system_prompt=VISUAL_GENERATOR_PROMPT,
        ),
        renderer="html",
    )


def token_matches(provided: str, expected: str) -> bool:
    return secrets.compare_digest(provided.encode(), expected.encode())


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def get(self) -> RuntimeSettings:
        with self._lock:
            return self._effective(self._read_overrides())

    def update(self, patch: SettingsPatch) -> RuntimeSettings:
        with self._lock:
            overrides = self._apply(self._read_overrides(), patch)
            self._write_overrides(overrides)
            return self._effective(overrides)

    def _effective(self, overrides: dict) -> RuntimeSettings:
        merged = defaults_from_env(get_settings()).model_dump()
        audio_override = overrides.get("audio")
        if isinstance(audio_override, dict):
            merged["audio"].update(audio_override)
        for section in ("script_drafter", "visual_generator", "renderer"):
            if section in overrides:
                merged[section] = overrides[section]
        return RuntimeSettings.model_validate(merged)

    def _read_overrides(self) -> dict:
        if not self.path.is_file():
            return {}
        return json.loads(self.path.read_text())

    def _write_overrides(self, overrides: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(overrides, indent=2) + "\n")
        temporary.replace(self.path)

    @staticmethod
    def _apply(overrides: dict, patch: SettingsPatch) -> dict:
        incoming = patch.model_dump(exclude_none=True)
        merged = dict(overrides)
        audio_patch = incoming.get("audio")
        if isinstance(audio_patch, dict):
            current_audio = merged.get("audio")
            if not isinstance(current_audio, dict):
                current_audio = {}
            merged["audio"] = {**current_audio, **audio_patch}
        for section in ("script_drafter", "visual_generator", "renderer"):
            if section in incoming:
                merged[section] = incoming[section]
        return merged


_store: SettingsStore | None = None


def get_store() -> SettingsStore:
    global _store
    if _store is None:
        _store = SettingsStore(Path(get_settings().settings_file))
    return _store


def reset_store() -> None:
    global _store
    _store = None
