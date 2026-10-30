"""Turn a topic into beats. The teacher reads these before any audio is made."""

import logging
import os

from pydantic import BaseModel, Field, model_validator

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent

from app.ai_client import AIError, build_model
from app.runtime_settings import get_store

logger = logging.getLogger(__name__)


class DraftBeat(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    text: str = Field(min_length=1, max_length=220)
    visual: str = Field(min_length=1, max_length=2000)
    checkpoint: bool = False


class DraftScript(BaseModel):
    beats: list[DraftBeat] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def beat_ids_must_be_unique(self) -> "DraftScript":
        ids = [beat.id for beat in self.beats]
        if len(ids) != len(set(ids)):
            raise ValueError("beat ids must be unique")
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
        logger.warning("script draft failed: %s", exc.__class__.__name__)
        raise AIError(f"Script generation failed: {exc.__class__.__name__}") from exc
    return [beat.model_dump() for beat in result.output.beats]
