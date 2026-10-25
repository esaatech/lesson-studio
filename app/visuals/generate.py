"""Ask the active model for one component, then record the end state in code."""

import logging
import os
from pathlib import Path

from pydantic import ValidationError

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent

from app.ai_client import AIError, build_model
from app.runtime_settings import get_store
from app.visuals.components import CHOICE_ADAPTER, VisualChoice, end_state_for
from app.visuals.cues import cues_for
from app.visuals.instruction import build_visual_instruction
from app.visuals.render_html import write_visual_page
from app.visuals.schema import ResolvedVisual, VisualBeat

logger = logging.getLogger(__name__)


def resolve_choice(beat: VisualBeat, choice: VisualChoice) -> ResolvedVisual:
    settings = choice.settings.model_dump()
    return ResolvedVisual(
        id=beat.id,
        component=choice.component,
        settings=settings,
        end_state=end_state_for(choice),
        duration=beat.duration,
        words=beat.words,
        cues=cues_for(choice.component, settings, beat.words, beat.duration),
        audio_file=beat.audio_file,
        checkpoint=beat.checkpoint,
        html_file="",
    )


def preview_visual(payload: dict, output_dir: Path | None = None) -> ResolvedVisual:
    """Build a page from a beat that already has its component. No model call."""
    beat = VisualBeat.model_validate(payload)
    choice = CHOICE_ADAPTER.validate_python(
        {"component": payload["component"], "settings": payload["settings"]}
    )
    visual = resolve_choice(beat, choice)
    page = write_visual_page(visual, output_dir or Path("output") / "visuals")
    visual.html_file = str(page)
    return visual


async def generate_visual(beat: VisualBeat, output_dir: Path | None = None) -> ResolvedVisual:
    task = get_store().get().visual_generator
    try:
        model = build_model(task)
    except AIError:
        raise
    agent = Agent(
        model,
        output_type=VisualChoice,
        instructions=build_visual_instruction(task.system_prompt),
        retries={"output": 2},
        model_settings={"temperature": task.temperature},
    )
    try:
        result = await agent.run(_user_prompt(beat))
        raw = result.output
        choice = raw if hasattr(raw, "settings") else CHOICE_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise AIError(f"The model returned a component the player cannot draw: {exc}") from exc
    except AIError:
        raise
    except Exception as exc:
        logger.warning("visual generation failed for %s: %s", beat.id, exc.__class__.__name__)
        raise AIError(f"Visual generation failed: {exc.__class__.__name__}") from exc

    visual = resolve_choice(beat, choice)
    page = write_visual_page(visual, output_dir or Path("output") / "visuals")
    visual.html_file = str(page)
    logger.info("visual %s component %s", beat.id, visual.component)
    return visual


def _user_prompt(beat: VisualBeat) -> str:
    return (
        "Choose a component for this beat.\n"
        f"{beat.model_dump_json(indent=2)}"
    )
