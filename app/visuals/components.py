"""Components the visual model is allowed to choose. Each one draws from progress p."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from app.beat_kind import parse_kind
from app.visuals.icons import ICON_LIST, ICON_NAMES

from app.beat_kind import parse_kind
from app.visuals.icons import ICON_LIST, ICON_NAMES

IconName = Literal[*ICON_NAMES]

_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
_PATH_D = re.compile(r"^[0-9eE.+,\sMLHVCSQTAZmlhvcsqtaz-]*$")


class DigitSlideSettings(BaseModel):
    digit: str = Field(min_length=1, max_length=3, description="Character that moves, such as 5")
    from_column: Literal["tens", "ones", "tenths", "hundredths"] = Field(description="Column where the digit starts")
    to_column: Literal["tens", "ones", "tenths", "hundredths"] = Field(description="Column where the digit finishes")
    label: str = Field(min_length=1, max_length=80, description="Caption revealed near the end")
    badge: str = Field(default="", max_length=20, description="Short badge such as ÷10")


class HighlightWordsSettings(BaseModel):
    sentence: str = Field(
        default="",
        max_length=400,
        description="The sentence students should see. Copy the On screen text. Never copy the spoken line.",
    )
    emphasis: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="Words in the On screen text that light up when they are also spoken",
    )


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
    sentence: str = Field(
        default="",
        max_length=400,
        description="The words students should see. Copy the On screen text. Never copy the spoken line. Empty On screen is a blank board.",
    )
    motion: Literal["highlight", "reveal"] = Field(
        description="highlight lights spoken words in a visible sentence. reveal brings each word in as it is said.",
    )


class WordTableSettings(BaseModel):
    title: str = Field(
        default="",
        max_length=48,
        description="Optional title above the table. Leave empty when the column names are enough.",
    )
    headers: list[str] = Field(
        min_length=2,
        max_length=3,
        description="Two or three column names. One or two words each.",
    )
    rows: list[list[str]] = Field(
        min_length=1,
        max_length=5,
        description="At most 5 rows. Each row has one short cell for every column, in header order. Use a table only when this beat has 5 or fewer pieces.",
    )

    @field_validator("headers")
    @classmethod
    def headers_are_short(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(item.split()) for item in value]
        if any(not item or len(item) > 24 for item in cleaned):
            raise ValueError("each column name is one or two short words")
        return cleaned

    @model_validator(mode="after")
    def rows_match_columns(self):
        width = len(self.headers)
        cleaned_rows: list[list[str]] = []
        for row in self.rows:
            cleaned = [" ".join(cell.split()) for cell in row]
            if len(cleaned) != width:
                raise ValueError("each row needs one cell for every column")
            if any(not cell or len(cell) > 40 for cell in cleaned):
                raise ValueError("each cell is a few words")
            cleaned_rows.append(cleaned)
        self.rows = cleaned_rows
        return self


class NumberedListSettings(BaseModel):
    title: str = Field(
        default="",
        max_length=48,
        description="Optional title. Leave empty when the numbers are enough.",
    )
    items: list[str] = Field(
        min_length=1,
        max_length=5,
        description="At most 5 short lines, in order. One line is a few words. Use a numbered list only when this beat has 5 or fewer pieces.",
    )

    @field_validator("items")
    @classmethod
    def items_are_short(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(item.split()) for item in value]
        if any(not item or len(item) > 80 for item in cleaned):
            raise ValueError("each line is a few words")
        return cleaned


IconName = Literal[*ICON_NAMES]


class IconChip(BaseModel):
    icon: IconName = Field(description=f"One of: {ICON_LIST}")
    label: str = Field(min_length=1, max_length=24, description="One or two spoken words under the icon")


class LabelPlusGroupSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="Topic title. We place it at the top.")
    badge: str = Field(default="", max_length=20, description="Tiny kicker on the word card, such as 1 word. Empty if none.")
    label: str = Field(min_length=1, max_length=24, description="The one word that stands for the group, such as flock")
    group_icon: IconName = Field(description=f"Icon for each member of the group. One of: {ICON_LIST}")
    count: int = Field(ge=2, le=6, description="How many members to stamp inside the ring, 2 to 6")
    caption: str = Field(default="", max_length=40, description="Short line under the ring, such as a whole group. Empty if the title is enough.")
    examples: list[IconChip] = Field(
        default_factory=list,
        max_length=4,
        description="Optional other examples along the bottom, each with an icon from the set",
    )


class CompareTwoSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="What is being compared")
    left_icon: IconName = Field(description=f"Icon for the first thing. One of: {ICON_LIST}")
    left_label: str = Field(min_length=1, max_length=24, description="Spoken name of the first thing")
    right_icon: IconName = Field(description=f"Icon for the second thing. One of: {ICON_LIST}")
    right_label: str = Field(min_length=1, max_length=24, description="Spoken name of the second thing")
    versus: str = Field(default="or", max_length=16, description="Short word between them, such as vs or or")


class PartWholeSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="The whole thing being named")
    whole_icon: IconName = Field(description=f"Icon for the whole. One of: {ICON_LIST}")
    whole_label: str = Field(min_length=1, max_length=24, description="Spoken name of the whole")
    parts: list[IconChip] = Field(min_length=2, max_length=4, description="Named parts of the whole")


class CauseEffectSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="The change being shown")
    cause_icon: IconName = Field(description=f"Icon for the cause. One of: {ICON_LIST}")
    cause_label: str = Field(min_length=1, max_length=24, description="Spoken cause")
    relation: str = Field(min_length=1, max_length=32, description="Short link on the arrow, such as leads to")
    effect_icon: IconName = Field(description=f"Icon for the effect. One of: {ICON_LIST}")
    effect_label: str = Field(min_length=1, max_length=24, description="Spoken effect")


class ProcessLoopSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="The cycle being shown")
    steps: list[IconChip] = Field(min_length=3, max_length=5, description="Steps around the loop, in order")


class SceneMark(BaseModel):
    kind: Literal["path", "rect", "circle", "line", "text"] = Field(
        description="path, rect, circle, line, or text"
    )
    d: str = Field(
        default="",
        max_length=800,
        description="SVG path in 0-100 local coordinates for kind path. Empty otherwise.",
    )
    x: float = Field(default=0, ge=0, le=100, description="x in 0-100 of this cell")
    y: float = Field(default=0, ge=0, le=100, description="y in 0-100 of this cell")
    x2: float = Field(default=0, ge=0, le=100, description="line end x in 0-100")
    y2: float = Field(default=0, ge=0, le=100, description="line end y in 0-100")
    w: float = Field(default=0, ge=0, le=100, description="rect width in 0-100")
    h: float = Field(default=0, ge=0, le=100, description="rect height in 0-100")
    r: float = Field(default=0, ge=0, le=50, description="circle radius in 0-50 of this cell")
    text: str = Field(default="", max_length=24, description="Short label inside the drawing. Empty if the cell label is enough.")
    fill: str = Field(default="none", max_length=7, description="none or a hex color such as #f6f3ec")
    stroke: str = Field(default="#2f6f4e", max_length=7, description="hex color such as #2f6f4e")

    @field_validator("fill")
    @classmethod
    def fill_is_safe(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned in {"", "none", "transparent"}:
            return "none"
        if _HEX.fullmatch(value.strip()):
            return value.strip()
        return "none"

    @field_validator("stroke")
    @classmethod
    def stroke_is_safe(cls, value: str) -> str:
        cleaned = value.strip()
        if _HEX.fullmatch(cleaned):
            return cleaned
        return "#2f6f4e"

    @field_validator("d")
    @classmethod
    def path_is_safe(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        if _PATH_D.fullmatch(cleaned):
            return cleaned[:800]
        return re.sub(r"[^0-9eE.+,\sMLHVCSQTAZmlhvcsqtaz-]", "", cleaned)[:800]


class SceneExample(BaseModel):
    cue: str = Field(min_length=1, max_length=32, description="Spoken word that reveals this example card")
    label: str = Field(min_length=1, max_length=24, description="One or two words under the icon")
    marks: list[SceneMark] = Field(
        min_length=1,
        max_length=6,
        description="Icon only, in 0-100 of the example cell. Do not draw the card or the label.",
    )


class ConceptSceneSettings(BaseModel):
    title: str = Field(min_length=1, max_length=48, description="Topic title. We place it at the top. Do not draw it again.")
    aside_badge: str = Field(default="", max_length=20, description="Tiny kicker on the word card, such as 1 word. Empty if none.")
    aside_label: str = Field(default="", max_length=24, description="The key word on a card to the left of the drawing. Empty if the drawing stands alone.")
    aside_cue: str = Field(default="", max_length=32, description="Spoken word that reveals the word card. Empty if aside_label is empty.")
    caption: str = Field(default="", max_length=40, description="Short line under the main drawing, such as a whole group.")
    main_cue: str = Field(min_length=1, max_length=32, description="Spoken word that reveals the main drawing")
    main_marks: list[SceneMark] = Field(
        min_length=1,
        max_length=8,
        description="The main picture only, in 0-100 of the main cell. Do not draw the title, word card, caption, or example row.",
    )
    examples: list[SceneExample] = Field(
        default_factory=list,
        max_length=4,
        description="Optional example cards along the bottom. We place the cards. You only draw the icon inside each one.",
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


class WordTableChoice(BaseModel):
    component: Literal["word-table"]
    settings: WordTableSettings


class NumberedListChoice(BaseModel):
    component: Literal["numbered-list"]
    settings: NumberedListSettings


class ConceptSceneChoice(BaseModel):
    component: Literal["concept-scene"]
    settings: ConceptSceneSettings


class LabelPlusGroupChoice(BaseModel):
    component: Literal["label-plus-group"]
    settings: LabelPlusGroupSettings


class CompareTwoChoice(BaseModel):
    component: Literal["compare-two"]
    settings: CompareTwoSettings


class PartWholeChoice(BaseModel):
    component: Literal["part-whole"]
    settings: PartWholeSettings


class CauseEffectChoice(BaseModel):
    component: Literal["cause-effect"]
    settings: CauseEffectSettings


class ProcessLoopChoice(BaseModel):
    component: Literal["process-loop"]
    settings: ProcessLoopSettings


IntroChoice = TitleCardChoice

WordingChoice = Annotated[
    KineticTextChoice | HighlightWordsChoice | NumberedListChoice | WordTableChoice | DigitSlideChoice | CodeLineChoice,
    Field(discriminator="component"),
]

ConceptChoice = Annotated[
    LabelPlusGroupChoice
    | CompareTwoChoice
    | PathTraceChoice
    | PartWholeChoice
    | CauseEffectChoice
    | MeasureChoice
    | ProcessLoopChoice,
    Field(discriminator="component"),
]

VisualChoice = Annotated[
    TitleCardChoice
    | KineticTextChoice
    | LabelPlusGroupChoice
    | CompareTwoChoice
    | PartWholeChoice
    | CauseEffectChoice
    | ProcessLoopChoice
    | DigitSlideChoice
    | HighlightWordsChoice
    | PathTraceChoice
    | CodeLineChoice
    | MeasureChoice
    | ConceptSceneChoice
    | LabelCalloutChoice
    | StrokeDiagramChoice
    | ShapePictureChoice
    | ArrowLinkChoice
    | BeforeAfterChoice
    | NumberedListChoice
    | WordTableChoice,
    Field(discriminator="component"),
]

CHOICE_ADAPTER = TypeAdapter(VisualChoice)

SETTING_MODELS = {
    "title-card": TitleCardSettings,
    "kinetic-text": KineticTextSettings,
    "label-plus-group": LabelPlusGroupSettings,
    "compare-two": CompareTwoSettings,
    "part-whole": PartWholeSettings,
    "cause-effect": CauseEffectSettings,
    "process-loop": ProcessLoopSettings,
    "digit-slide": DigitSlideSettings,
    "highlight-words": HighlightWordsSettings,
    "numbered-list": NumberedListSettings,
    "word-table": WordTableSettings,
    "path-trace": PathTraceSettings,
    "code-line": CodeLineSettings,
    "measure": MeasureSettings,
    "concept-scene": ConceptSceneSettings,
    "label-callout": LabelCalloutSettings,
    "stroke-diagram": StrokeDiagramSettings,
    "shape-picture": ShapePictureSettings,
    "arrow-link": ArrowLinkSettings,
    "before-after": BeforeAfterSettings,
}

USE_WHEN = {
    "title-card": "Intro only. Name the lesson, or the section that is starting. Large title, optional subtitle, optional one emblem. Not an explanation.",
    "kinetic-text": "Wording. One sentence. Students see the On screen text only. Empty On screen is blank. To show the spoken line, it must be copied into On screen. Also use this when the beat has more than 5 pieces, so nothing is left off the frame.",
    "digit-slide": "Wording. Only when one digit moves between place-value columns.",
    "highlight-words": "Wording. One sentence. Students see the On screen sentence only. Emphasis marks spoken words that already appear on screen. Also use this when the beat has more than 5 pieces, so nothing is left off the frame.",
    "numbered-list": "Wording. Use this when On screen is a short sequence of examples, questions, types, or other pieces of the same kind, and there are 5 or fewer. Do not use this when the beat has more than 5 pieces.",
    "word-table": "Wording. Use this when those pieces fall into columns, such as a word, its plural, and the rule, and there are 5 or fewer. At most 5 rows and 3 columns. Do not use this when the beat has more than 5 pieces.",
    "code-line": "Wording. One line of code, with the important tokens marked.",
    "label-plus-group": "Concept. One word stands for many things. A label, a ring of the same icon, optional other examples. English flock, math set, science species.",
    "compare-two": "Concept. Two things side by side. Noun vs verb, odd vs even, plant vs animal cell.",
    "path-trace": "Concept. Steps along a single line, in order.",
    "part-whole": "Concept. Named parts of one whole. Sentence parts, fractions, parts of a plant.",
    "cause-effect": "Concept. This leads to that. Punctuation changes meaning, adding raises the total, heat evaporates water.",
    "measure": "Concept. A number line or a bar that fills as quantities are spoken.",
    "process-loop": "Concept. A cycle that returns to the start. Life cycle, water cycle, seasons.",
}

CONCEPT_COMPONENTS = (
    "label-plus-group",
    "compare-two",
    "path-trace",
    "part-whole",
    "cause-effect",
    "measure",
    "process-loop",
)

COMPONENTS_FOR_KIND = {
    "intro": ("title-card",),
    "wording": ("kinetic-text", "highlight-words", "numbered-list", "word-table", "digit-slide", "code-line"),
    "concept": CONCEPT_COMPONENTS,
}

CHOICE_TYPE_FOR_KIND = {
    "intro": IntroChoice,
    "wording": WordingChoice,
    "concept": ConceptChoice,
}


def choice_type_for(kind: str | None):
    """The pydantic output type the visual model may return for this beat kind."""
    resolved = parse_kind(kind)
    if resolved in CHOICE_TYPE_FOR_KIND:
        return CHOICE_TYPE_FOR_KIND[resolved]
    return VisualChoice


def component_catalog(kind: str | None = None) -> str:
    """The component list appended to the system instruction at call time."""
    resolved = parse_kind(kind)
    if resolved in COMPONENTS_FOR_KIND:
        names = COMPONENTS_FOR_KIND[resolved]
        lines = [f"This beat kind is {resolved}. Choose only from these components."]
    else:
        names = COMPONENTS_FOR_KIND["intro"] + COMPONENTS_FOR_KIND["wording"] + COMPONENTS_FOR_KIND["concept"]
        lines = [
            "Allowed components. Match the beat kind: intro uses title-card, wording uses kinetic text, concept uses a relationship structure. If no structure fits, wording is the fallback."
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
    if isinstance(choice, LabelPlusGroupChoice):
        return {
            "component": "label-plus-group",
            "title": settings.title,
            "label": settings.label,
            "group_icon": settings.group_icon,
            "examples": [item.label for item in settings.examples],
        }
    if isinstance(choice, CompareTwoChoice):
        return {
            "component": "compare-two",
            "title": settings.title,
            "left": settings.left_label,
            "right": settings.right_label,
        }
    if isinstance(choice, PartWholeChoice):
        return {
            "component": "part-whole",
            "title": settings.title,
            "whole": settings.whole_label,
            "parts": [item.label for item in settings.parts],
        }
    if isinstance(choice, CauseEffectChoice):
        return {
            "component": "cause-effect",
            "title": settings.title,
            "cause": settings.cause_label,
            "effect": settings.effect_label,
        }
    if isinstance(choice, ProcessLoopChoice):
        return {
            "component": "process-loop",
            "title": settings.title,
            "steps": [item.label for item in settings.steps],
        }
    if isinstance(choice, ConceptSceneChoice):
        return {
            "component": "concept-scene",
            "title": settings.title,
            "aside": settings.aside_label,
            "caption": settings.caption,
            "examples": [item.label for item in settings.examples],
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
    if isinstance(choice, NumberedListChoice):
        return {"component": "numbered-list", "items": settings.items}
    if isinstance(choice, WordTableChoice):
        return {"component": "word-table", "headers": settings.headers, "rows": settings.rows}
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
