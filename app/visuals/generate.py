"""Ask the active model for one component, then record the end state in code."""

import asyncio
import logging
import os
from pathlib import Path

from pydantic import ValidationError

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent

from app.ai_client import AIError, build_model
from app.runtime_settings import AITaskSettings, get_store
from app.visuals.components import CHOICE_ADAPTER, VisualChoice, choice_type_for, end_state_for
from app.visuals.cues import cues_for
from app.visuals.instruction import build_visual_instruction
from app.visuals.render_html import write_visual_page
from app.visuals.schema import ResolvedVisual, VisualBeat

logger = logging.getLogger(__name__)

_RETRYABLE = frozenset({"ModelRateLimitError", "ModelUnavailableError"})
_RETRY_WAITS = (20.0, 40.0, 60.0, 60.0, 60.0)


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


async def generate_visual(
    beat: VisualBeat,
    output_dir: Path | None = None,
    task: AITaskSettings | None = None,
) -> ResolvedVisual:
    task = task or get_store().get().visual_generator
    try:
        model = build_model(task)
    except AIError:
        raise
    agent = Agent(
        model,
        output_type=choice_type_for(beat.kind),
        instructions=build_visual_instruction(task.system_prompt, beat.kind),
        retries={"output": 2},
        model_settings={"temperature": task.temperature},
    )
    try:
        result = await _run_visual_agent(agent, beat)
        raw = result.output
        choice = raw if hasattr(raw, "settings") else CHOICE_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise AIError(f"The model returned a component the player cannot draw: {exc}") from exc
    except AIError:
        raise

    visual = resolve_choice(beat, choice)
    page = write_visual_page(visual, output_dir or Path("output") / "visuals")
    visual.html_file = str(page)
    logger.info("visual %s component %s", beat.id, visual.component)
    return visual


async def _run_visual_agent(agent: Agent, beat: VisualBeat):
    prompt = _user_prompt(beat)
    attempts = len(_RETRY_WAITS) + 1
    for attempt in range(attempts):
        try:
            return await agent.run(prompt)
        except ValidationError:
            raise
        except AIError:
            raise
        except Exception as exc:
            wait = _RETRY_WAITS[attempt] if attempt < len(_RETRY_WAITS) else None
            if exc.__class__.__name__ in _RETRYABLE and wait is not None:
                logger.warning(
                    "visual generation %s hit %s, retrying in %.0fs",
                    beat.id,
                    exc.__class__.__name__,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            logger.warning("visual generation failed for %s: %s", beat.id, exc.__class__.__name__)
            raise AIError(_visual_error(beat, exc)) from exc
    raise AIError(_visual_error(beat, RuntimeError("retries exhausted")))


def _visual_error(beat: VisualBeat, exc: BaseException) -> str:
    name = exc.__class__.__name__
    if name == "ModelRateLimitError":
        return (
            f"Google rate-limited picture {beat.id} (too many picture calls in a minute). "
            "Wait a minute and approve again."
        )
    if name == "ModelUnavailableError":
        return (
            f"The picture model is overloaded on {beat.id}. "
            "Try Gemini 3.5 Flash Lite, or approve again in a few minutes."
        )
    return f"Visual generation failed for {beat.id}: {name}"


def _user_prompt(beat: VisualBeat) -> str:
    kind = beat.kind or "unknown"
    return (
        f"Choose a component for this beat. The beat kind is {kind}.\n"
        f"{beat.model_dump_json(indent=2)}"
    )
