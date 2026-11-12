"""Ask the active model for one component, then record the end state in code."""

import asyncio
import logging
import os
import re
from pathlib import Path

from pydantic import ValidationError

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent

from app.ai_client import AIError, build_model
from app.runtime_settings import AITaskSettings, get_store
from app.beat_kind import parse_kind
from app.visuals.components import CHOICE_ADAPTER, COMPONENTS_FOR_KIND, VisualChoice, choice_type_for, end_state_for
from app.visuals.cues import _content_tokens, cues_for
from app.visuals.instruction import build_visual_instruction
from app.visuals.render_html import write_visual_page
from app.visuals.schema import ResolvedVisual, VisualBeat

logger = logging.getLogger(__name__)

_RETRYABLE = frozenset({"ModelRateLimitError", "ModelUnavailableError"})
_RETRY_WAITS = (20.0, 40.0, 60.0, 60.0, 60.0)


def _piece_count(visual: str) -> int:
    """How many examples, questions, or types On screen already lists."""
    text = (visual or "").strip()
    if not text:
        return 0
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return len(lines)
    arrows = text.count("→")
    if arrows >= 2:
        return arrows
    numbered = re.findall(r"(?:^|\s)\d+[\.\)]\s+\S", text)
    if len(numbered) >= 2:
        return len(numbered)
    return 1


def apply_on_screen_words(beat: VisualBeat, choice: VisualChoice) -> VisualChoice:
    """Wording slides use On screen only. Spoken text is never copied onto the board."""
    if choice.component in {"numbered-list", "word-table"} and _piece_count(beat.visual) > 5:
        sentence = (beat.visual or "").strip()[:400]
        return CHOICE_ADAPTER.validate_python(
            {"component": "kinetic-text", "settings": {"sentence": sentence, "motion": "highlight"}}
        )
    if choice.component not in {"kinetic-text", "highlight-words"}:
        return choice
    sentence = (beat.visual or "").strip()[:400]
    data = choice.settings.model_dump()
    data["sentence"] = sentence
    shown = set(_content_tokens(sentence))
    if choice.component == "kinetic-text" and data.get("motion") == "reveal":
        spoken = _content_tokens(beat.text)
        overlap = sum(1 for token in spoken if token in shown) if spoken else 0
        if not sentence or not spoken or overlap / len(spoken) < 0.4:
            data["motion"] = "highlight"
    if choice.component == "highlight-words":
        kept = [
            phrase
            for phrase in data.get("emphasis") or []
            if any(token in shown for token in _content_tokens(str(phrase)))
        ]
        if not kept:
            kept = [token for token in _content_tokens(beat.text) if token in shown][:12]
        data["emphasis"] = kept
    return CHOICE_ADAPTER.validate_python({"component": choice.component, "settings": data})


def resolve_choice(beat: VisualBeat, choice: VisualChoice) -> ResolvedVisual:
    choice = apply_on_screen_words(beat, choice)
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

    kind = parse_kind(beat.kind)
    allowed = COMPONENTS_FOR_KIND.get(kind or "")
    if allowed and choice.component not in allowed:
        raise AIError(f"The picture for a {kind} line cannot be {choice.component}.")

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
    kind = parse_kind(beat.kind) or "unknown"
    return (
        f"Choose a component for this beat. The beat kind is {kind}.\n"
        f"{beat.model_dump_json(indent=2)}"
    )
