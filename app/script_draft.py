"""Turn a topic into beats. The teacher reads these before any audio is made."""

import logging
import os
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.beat_kind import BeatKind, parse_kind

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent

from app.ai_client import AIError, build_model
from app.runtime_settings import get_store

logger = logging.getLogger(__name__)


class DraftBeat(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    text: str = Field(min_length=1, max_length=220)
    kind: BeatKind
    visual: str = Field(min_length=1, max_length=2000)
    checkpoint: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def id_is_safe(cls, value: object) -> str:
        raw = re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:63]
        if not raw:
            return "line"
        if raw[0].isdigit():
            raw = f"b{raw}"[:64]
        return raw

    @field_validator("text", mode="before")
    @classmethod
    def text_stays_one_breath(cls, value: object) -> str:
        return _clip(value, 220)

    @field_validator("visual", mode="before")
    @classmethod
    def visual_stays_on_the_board(cls, value: object) -> str:
        return _clip(value, 2000)

    @field_validator("kind", mode="before")
    @classmethod
    def kind_is_known(cls, value: object) -> str:
        return parse_kind(value, "concept") or "concept"


class DraftScript(BaseModel):
    beats: list[DraftBeat] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def beat_ids_must_be_unique(self) -> "DraftScript":
        seen: set[str] = set()
        for index, beat in enumerate(self.beats, start=1):
            candidate = beat.id
            if candidate in seen:
                candidate = f"b{index}"
                while candidate in seen:
                    candidate = f"b{index}x{len(seen)}"
            beat.id = candidate
            seen.add(candidate)
        return self


async def draft_beats(topic: str) -> list[dict]:
    task = get_store().get().script_drafter
    model = build_model(task)
    agent = Agent(
        model,
        output_type=DraftScript,
        instructions=task.system_prompt,
        retries={"output": 2},
        model_settings={"temperature": task.temperature},
    )
    try:
        result = await agent.run(topic.strip())
    except AIError:
        raise
    except Exception as exc:
        detail = _draft_failure(exc)
        logger.warning("script draft failed: %s", detail)
        raise AIError(f"Script generation failed: {detail}") from exc
    return [beat.model_dump() for beat in result.output.beats]


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].strip()
    return cut or text[:limit]


def _draft_failure(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = " ".join(str(current).split())
        if message and message not in parts:
            parts.append(message)
        current = current.__cause__
    text = " — ".join(parts) if parts else exc.__class__.__name__
    return text[:400]
