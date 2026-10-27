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
Return JSON only. Each beat has id, text, visual, and checkpoint.
text is one spoken sentence. visual describes the picture a student watches during that sentence.
Describe a diagram being drawn, a simple object with labels, two things joined by an arrow, a before and an after, one line of code, or a number line or bar.
Describe a highlighted sentence only when the lesson is about those exact words.
checkpoint is true only when the lesson should pause for the student.
Use the subject, grade, and objective you are given. Do not write HTML."""

VISUAL_GENERATOR_PROMPT = """You choose a drawing component for one lesson beat.
Use the narration, the visual description, the duration, and the previous end state.
Prefer a drawn picture when the beat explains an object, a relationship, a change, a line of code, or a quantity.
Use highlight-words only when the point of the beat is the wording itself.
Use digit-slide only when one digit moves between place-value columns.
On-screen words must be words that are actually spoken, so each part can appear on time.
The picture must be a function of progress p, from 0 to 1. The same p always shows the same frame.
Return JSON only. Do not write HTML, CSS, or JavaScript.
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
