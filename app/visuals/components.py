"""Components the visual model is allowed to choose. Each one draws from progress p."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class DigitSlideSettings(BaseModel):
    digit: str = Field(min_length=1, max_length=3, description="Character that moves, such as 5")
    from_column: Literal["tens", "ones", "tenths", "hundredths"] = Field(description="Column where the digit starts")
    to_column: Literal["tens", "ones", "tenths", "hundredths"] = Field(description="Column where the digit finishes")
    label: str = Field(min_length=1, max_length=80, description="Caption revealed near the end")
    badge: str = Field(default="", max_length=20, description="Short badge such as ÷10")


class HighlightWordsSettings(BaseModel):
    sentence: str = Field(min_length=1, max_length=400, description="Full sentence shown on screen")
    emphasis: list[str] = Field(min_length=1, max_length=12, description="Words that light up in order as p increases")


class CalloutPart(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=120)


class LabelCalloutSettings(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="Diagram title")
    parts: list[CalloutPart] = Field(min_length=1, max_length=6, description="Parts that appear one by one")


class PathTraceSettings(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="What the path is showing")
    steps: list[str] = Field(min_length=2, max_length=6, description="Labels along the path, in order")


class DigitSlideChoice(BaseModel):
    component: Literal["digit-slide"]
    settings: DigitSlideSettings


class HighlightWordsChoice(BaseModel):
    component: Literal["highlight-words"]
    settings: HighlightWordsSettings


class LabelCalloutChoice(BaseModel):
    component: Literal["label-callout"]
    settings: LabelCalloutSettings


class PathTraceChoice(BaseModel):
    component: Literal["path-trace"]
    settings: PathTraceSettings


VisualChoice = Annotated[
    DigitSlideChoice | HighlightWordsChoice | LabelCalloutChoice | PathTraceChoice,
    Field(discriminator="component"),
]

CHOICE_ADAPTER = TypeAdapter(VisualChoice)

SETTING_MODELS = {
    "digit-slide": DigitSlideSettings,
    "highlight-words": HighlightWordsSettings,
    "label-callout": LabelCalloutSettings,
    "path-trace": PathTraceSettings,
}


def component_catalog() -> str:
    """The component list appended to the system instruction at call time."""
    lines = ["Allowed components:"]
    for name, model in SETTING_MODELS.items():
        fields = []
        for field_name, field in model.model_fields.items():
            description = field.description or field_name
            fields.append(f"{field_name}: {description}")
        lines.append(f"- {name} ({'; '.join(fields)})")
    return "\n".join(lines)


def end_state_for(choice: DigitSlideChoice | HighlightWordsChoice | LabelCalloutChoice | PathTraceChoice) -> dict:
    """What is on screen at p = 1. The next beat can start from this."""
    if isinstance(choice, DigitSlideChoice):
        settings = choice.settings
        return {
            "component": "digit-slide",
            "digit": settings.digit,
            "column": settings.to_column,
            "label": settings.label,
            "badge": settings.badge,
        }
    if isinstance(choice, HighlightWordsChoice):
        settings = choice.settings
        return {
            "component": "highlight-words",
            "sentence": settings.sentence,
            "emphasized": settings.emphasis,
        }
    if isinstance(choice, LabelCalloutChoice):
        settings = choice.settings
        return {
            "component": "label-callout",
            "title": settings.title,
            "visible_parts": [part.name for part in settings.parts],
        }
    settings = choice.settings
    return {
        "component": "path-trace",
        "title": settings.title,
        "completed_steps": settings.steps,
    }
