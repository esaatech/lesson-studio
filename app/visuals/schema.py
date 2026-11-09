from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.beat_kind import BeatKind, parse_kind
from app.runtime_settings import AITaskSettings


class WordTime(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class VisualBeat(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    text: str = Field(min_length=1, max_length=2000)
    visual: str = Field(default="", max_length=2000)
    kind: BeatKind | None = None
    checkpoint: bool = False
    duration: float | None = Field(default=None, ge=0)
    previous_end_state: dict[str, Any] | None = None
    words: list[WordTime] = Field(default_factory=list)
    audio_file: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def stored_kind_is_current(cls, value: object) -> str | None:
        return parse_kind(value)


class ResolvedVisual(BaseModel):
    id: str
    component: str
    settings: dict[str, Any]
    end_state: dict[str, Any]
    duration: float | None = None
    words: list[WordTime] = Field(default_factory=list)
    cues: dict[str, float] = Field(default_factory=dict)
    audio_file: str = ""
    checkpoint: bool = False
    html_file: str


class VisualRunRequest(VisualBeat):
    generate_audio: bool = False
    visual_generator: AITaskSettings | None = None


class VisualRunResponse(ResolvedVisual):
    html: str = ""
