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
    emphasis: list[str] = Field(min_length=1, max_length=12, description="Words that light up in order as they are spoken")


class CalloutPart(BaseModel):
    name: str = Field(min_length=1, max_length=24, description="One or two words")
    detail: str = Field(default="", max_length=48, description="A few words of detail")


class LabelCalloutSettings(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="Diagram title")
    parts: list[CalloutPart] = Field(min_length=1, max_length=4, description="Up to four parts that appear one by one")


class PathTraceSettings(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="What the path is showing")
    steps: list[str] = Field(min_length=2, max_length=4, description="Short labels along the path, in order")


class StrokeMark(BaseModel):
    shape: Literal["circle", "box", "arrow"] = Field(description="circle, box, or arrow")
    text: str = Field(min_length=1, max_length=24, description="One or two spoken words under the shape")


class StrokeDiagramSettings(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="Diagram title, shown the whole time")
    marks: list[StrokeMark] = Field(min_length=1, max_length=3, description="Up to three shapes that draw themselves when their label is spoken")


class ShapePictureSettings(BaseModel):
    subject: Literal["box", "house", "book", "sun", "tree", "computer", "person", "ball", "clock", "star"] = Field(
        description="Object that is drawn: box, house, book, sun, tree, computer, person, ball, clock, or star"
    )
    title: str = Field(min_length=1, max_length=80, description="Caption beside the drawing")
    labels: list[str] = Field(min_length=1, max_length=3, description="Up to three labels of one or two words")


class ArrowLinkSettings(BaseModel):
    left: str = Field(min_length=1, max_length=32, description="One or two spoken words on the left")
    relation: str = Field(min_length=1, max_length=40, description="Short relationship written on the arrow, such as on, contains, or becomes")
    right: str = Field(min_length=1, max_length=32, description="One or two spoken words on the right")


class BeforeAfterSettings(BaseModel):
    before_label: str = Field(min_length=1, max_length=24, description="Small label on the first card, such as Before")
    before_text: str = Field(min_length=1, max_length=80, description="What is true first. Use words that are spoken.")
    after_label: str = Field(min_length=1, max_length=24, description="Small label on the second card, such as After")
    after_text: str = Field(min_length=1, max_length=80, description="What is true after the change. Use words that are spoken.")


class CodeLineSettings(BaseModel):
    code: str = Field(min_length=1, max_length=160, description="One line of code, shown in full from the start")
    focus: list[str] = Field(min_length=1, max_length=8, description="Tokens in that line that light up when spoken")


class MeasureSettings(BaseModel):
    kind: Literal["number-line", "bar"] = Field(description="number-line or bar")
    title: str = Field(min_length=1, max_length=80, description="Title shown the whole time")
    start_label: str = Field(min_length=1, max_length=20, description="Left end, such as 0")
    end_label: str = Field(min_length=1, max_length=20, description="Right end, such as 10")
    marks: list[str] = Field(min_length=1, max_length=5, description="Spoken points that appear in order along the line or as the bar fills")
    caption: str = Field(default="", max_length=80, description="Sentence shown when the measure is complete. Empty if the title is enough.")


class TitleCardSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="The lesson name, a few words, shown large")
    subtitle: str = Field(default="", max_length=80, description="Optional second line. Empty if the title is enough.")
    emblem: Literal["none", "clock", "book", "sun", "star", "person", "tree", "house"] = Field(
        default="none",
        description="Optional simple drawing under the title: none, clock, book, sun, star, person, tree, or house",
    )


class KineticTextSettings(BaseModel):
    sentence: str = Field(min_length=1, max_length=400, description="The words students should see, taken from the spoken line")
    motion: Literal["highlight", "reveal"] = Field(
        description="highlight lights spoken words in a visible sentence. reveal brings each word in as it is said.",
    )


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


class StrokeDiagramChoice(BaseModel):
    component: Literal["stroke-diagram"]
    settings: StrokeDiagramSettings


class ShapePictureChoice(BaseModel):
    component: Literal["shape-picture"]
    settings: ShapePictureSettings


class ArrowLinkChoice(BaseModel):
    component: Literal["arrow-link"]
    settings: ArrowLinkSettings


class BeforeAfterChoice(BaseModel):
    component: Literal["before-after"]
    settings: BeforeAfterSettings


class CodeLineChoice(BaseModel):
    component: Literal["code-line"]
    settings: CodeLineSettings


class MeasureChoice(BaseModel):
    component: Literal["measure"]
    settings: MeasureSettings


class TitleCardChoice(BaseModel):
    component: Literal["title-card"]
    settings: TitleCardSettings


class KineticTextChoice(BaseModel):
    component: Literal["kinetic-text"]
    settings: KineticTextSettings


IntroChoice = TitleCardChoice

WordingChoice = Annotated[
    KineticTextChoice | HighlightWordsChoice | DigitSlideChoice | CodeLineChoice,
    Field(discriminator="component"),
]

ConceptChoice = Annotated[
    LabelCalloutChoice
    | PathTraceChoice
    | StrokeDiagramChoice
    | ShapePictureChoice
    | ArrowLinkChoice
    | BeforeAfterChoice
    | MeasureChoice,
    Field(discriminator="component"),
]

VisualChoice = Annotated[
    TitleCardChoice
    | KineticTextChoice
    | DigitSlideChoice
    | HighlightWordsChoice
    | LabelCalloutChoice
    | PathTraceChoice
    | StrokeDiagramChoice
    | ShapePictureChoice
    | ArrowLinkChoice
    | BeforeAfterChoice
    | CodeLineChoice
    | MeasureChoice,
    Field(discriminator="component"),
]

CHOICE_ADAPTER = TypeAdapter(VisualChoice)

SETTING_MODELS = {
    "title-card": TitleCardSettings,
    "kinetic-text": KineticTextSettings,
    "digit-slide": DigitSlideSettings,
    "highlight-words": HighlightWordsSettings,
    "label-callout": LabelCalloutSettings,
    "path-trace": PathTraceSettings,
    "stroke-diagram": StrokeDiagramSettings,
    "shape-picture": ShapePictureSettings,
    "arrow-link": ArrowLinkSettings,
    "before-after": BeforeAfterSettings,
    "code-line": CodeLineSettings,
    "measure": MeasureSettings,
}

USE_WHEN = {
    "title-card": "Intro only. Name the lesson. Large title, optional subtitle, optional one emblem. Not an explanation.",
    "kinetic-text": "Wording. The spoken language is what students see, highlighted or revealed as it is said.",
    "digit-slide": "Wording. Only when one digit moves between place-value columns.",
    "highlight-words": "Wording. Only when the point of the beat is the wording of one sentence.",
    "label-callout": "Concept. A short list of named parts, with no drawn object.",
    "path-trace": "Concept. Steps along a single line.",
    "stroke-diagram": "Concept. A few shapes that draw themselves while they are named.",
    "shape-picture": "Concept. A concrete object the student should see, with labels.",
    "arrow-link": "Concept. Two things and the relationship between them.",
    "before-after": "Concept. A change from one state to another.",
    "code-line": "Wording. One line of code, with the important tokens marked.",
    "measure": "Concept. A number line or a bar that fills as quantities are spoken.",
}

COMPONENTS_FOR_KIND = {
    "intro": ("title-card",),
    "wording": ("kinetic-text", "highlight-words", "digit-slide", "code-line"),
    "concept": (
        "label-callout",
        "path-trace",
        "stroke-diagram",
        "shape-picture",
        "arrow-link",
        "before-after",
        "measure",
    ),
}

CHOICE_TYPE_FOR_KIND = {
    "intro": IntroChoice,
    "wording": WordingChoice,
    "concept": ConceptChoice,
}


def choice_type_for(kind: str | None):
    """The pydantic output type the visual model may return for this beat kind."""
    if kind in CHOICE_TYPE_FOR_KIND:
        return CHOICE_TYPE_FOR_KIND[kind]
    return VisualChoice


def component_catalog(kind: str | None = None) -> str:
    """The component list appended to the system instruction at call time."""
    if kind in COMPONENTS_FOR_KIND:
        names = COMPONENTS_FOR_KIND[kind]
        lines = [f"This beat kind is {kind}. Choose only from these components."]
    else:
        names = tuple(SETTING_MODELS)
        lines = [
            "Allowed components. Match the beat kind: intro uses title-card, wording uses kinetic text, concept uses a drawing of the idea."
        ]
    for name in names:
        model = SETTING_MODELS[name]
        fields = []
        for field_name, field in model.model_fields.items():
            description = field.description or field_name
            fields.append(f"{field_name}: {description}")
        lines.append(f"- {name} ({'; '.join(fields)}) {USE_WHEN[name]}")
    return "\n".join(lines)


def end_state_for(choice: VisualChoice) -> dict:
    """What is on screen at p = 1. The next beat can start from this."""
    settings = choice.settings
    if isinstance(choice, TitleCardChoice):
        return {
            "component": "title-card",
            "title": settings.title,
            "subtitle": settings.subtitle,
            "emblem": settings.emblem,
        }
    if isinstance(choice, KineticTextChoice):
        return {
            "component": "kinetic-text",
            "sentence": settings.sentence,
            "motion": settings.motion,
        }
    if isinstance(choice, DigitSlideChoice):
        return {
            "component": "digit-slide",
            "digit": settings.digit,
            "column": settings.to_column,
            "label": settings.label,
            "badge": settings.badge,
        }
    if isinstance(choice, HighlightWordsChoice):
        return {
            "component": "highlight-words",
            "sentence": settings.sentence,
            "emphasized": settings.emphasis,
        }
    if isinstance(choice, LabelCalloutChoice):
        return {
            "component": "label-callout",
            "title": settings.title,
            "visible_parts": [part.name for part in settings.parts],
        }
    if isinstance(choice, PathTraceChoice):
        return {
            "component": "path-trace",
            "title": settings.title,
            "completed_steps": settings.steps,
        }
    if isinstance(choice, StrokeDiagramChoice):
        return {
            "component": "stroke-diagram",
            "title": settings.title,
            "visible_marks": [mark.text for mark in settings.marks],
        }
    if isinstance(choice, ShapePictureChoice):
        return {
            "component": "shape-picture",
            "subject": settings.subject,
            "title": settings.title,
            "labels": settings.labels,
        }
    if isinstance(choice, ArrowLinkChoice):
        return {
            "component": "arrow-link",
            "left": settings.left,
            "relation": settings.relation,
            "right": settings.right,
        }
    if isinstance(choice, BeforeAfterChoice):
        return {
            "component": "before-after",
            "before": settings.before_text,
            "after": settings.after_text,
        }
    if isinstance(choice, CodeLineChoice):
        return {
            "component": "code-line",
            "code": settings.code,
            "focused": settings.focus,
        }
    return {
        "component": "measure",
        "kind": settings.kind,
        "title": settings.title,
        "marks": settings.marks,
        "caption": settings.caption,
    }
