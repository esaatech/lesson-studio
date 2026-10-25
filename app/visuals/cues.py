"""Map word times onto a component. The same time always produces the same frame."""

from app.visuals.schema import WordTime

_NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "point",
}


def bare_word(word: str) -> str:
    return "".join(character for character in word.lower() if character.isalnum())


def digit_slide_cues(to_column: str, words: list[WordTime], duration: float) -> dict[str, float]:
    """The digit arrives when the column is first named. The label appears on the later phrase."""
    column = bare_word(to_column)
    matches = [word for word in words if bare_word(word.word) == column]
    if not matches:
        slide_end = duration
        label_start = round(duration * 0.72, 3)
        label_end = duration
    else:
        slide_end = matches[0].end
        if len(matches) >= 2:
            second = matches[1]
            index = words.index(second)
            previous = words[index - 1] if index > 0 else None
            if previous is not None and bare_word(previous.word) in _NUMBER_WORDS:
                label_start = previous.start
            else:
                label_start = second.start
            label_end = second.end
        else:
            label_start = slide_end
            label_end = duration
    return {
        "slide_end": round(slide_end, 3),
        "label_start": round(label_start, 3),
        "label_end": round(label_end, 3),
        "badge_start": round(label_start, 3),
        "badge_end": round(label_end, 3),
    }


def cues_for(component: str, settings: dict, words: list[WordTime], duration: float | None) -> dict[str, float]:
    length = duration if duration is not None else (words[-1].end if words else 1.0)
    if component == "digit-slide":
        return digit_slide_cues(str(settings.get("to_column", "")), words, length)
    return {}
