"""Map word times onto a component. The same time always produces the same frame."""

import re

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


_TOKEN_GAP = 8


def _content_tokens(text: str) -> list[str]:
    parts = re.split(r"[\s/]+", text.strip())
    return [token for token in (bare_word(part) for part in parts) if token]


def _same_token(left: str, right: str) -> bool:
    if left == right:
        return True
    return len(left) >= 5 and len(right) >= 5 and (left.startswith(right) or right.startswith(left))


def _find_sequence(tokens: list[str], spoken: list[str], start: int) -> tuple[int, int] | None:
    for index in range(start, len(spoken)):
        if not _same_token(spoken[index], tokens[0]):
            continue
        cursor = index
        last = index
        matched = True
        for token in tokens[1:]:
            found = None
            for follow in range(cursor + 1, min(len(spoken), cursor + 1 + _TOKEN_GAP)):
                if _same_token(spoken[follow], token):
                    found = follow
                    break
            if found is None:
                matched = False
                break
            cursor = found
            last = found
        if matched:
            return index, last
    return None


def _find_phrase(tokens: list[str], spoken: list[str], start: int) -> tuple[int, int] | None:
    if not tokens:
        return None
    sequence = _find_sequence(tokens, spoken, start)
    if sequence is not None:
        return sequence
    for token in tokens:
        for index in range(start, len(spoken)):
            if _same_token(spoken[index], token):
                return index, index
    return None


def reveal_times(phrases: list[str], words: list[WordTime], duration: float) -> list[float]:
    """When each on-screen phrase appears. Spoken words win over an even split of the beat."""
    spoken = [bare_word(word.word) for word in words]
    cursor = 0
    found: list[float | None] = []
    for phrase in phrases:
        match = _find_phrase(_content_tokens(phrase), spoken, cursor)
        if match is None:
            found.append(None)
            continue
        start_index, end_index = match
        found.append(words[start_index].start)
        cursor = end_index + 1
    return _fill_reveal_times(found, duration)


def _fill_reveal_times(found: list[float | None], duration: float) -> list[float]:
    count = len(found)
    if count == 0:
        return []
    if all(item is None for item in found):
        if count == 1:
            return [0.0]
        return [round(duration * index / count, 3) for index in range(count)]
    known = [(index, item) for index, item in enumerate(found) if item is not None]
    filled = [0.0] * count
    first_index, first_time = known[0]
    for index in range(first_index + 1):
        filled[index] = first_time
    for (left_index, left_time), (right_index, right_time) in zip(known, known[1:]):
        filled[left_index] = left_time
        gap = right_index - left_index
        for step, index in enumerate(range(left_index + 1, right_index), start=1):
            filled[index] = left_time + (right_time - left_time) * step / gap
    last_index, last_time = known[-1]
    filled[last_index] = last_time
    for index in range(last_index + 1, count):
        filled[index] = last_time
    for index in range(1, count):
        if filled[index] < filled[index - 1]:
            filled[index] = filled[index - 1]
    return [round(item, 3) for item in filled]


def _reveal_cues(phrases: list[str], words: list[WordTime], duration: float) -> dict[str, float]:
    return {f"reveal_{index}": time for index, time in enumerate(reveal_times(phrases, words, duration))}


def _part_names(parts: list) -> list[str]:
    names = []
    for part in parts:
        if isinstance(part, dict):
            names.append(str(part.get("name", "")))
        else:
            names.append(str(part))
    return names


def cues_for(component: str, settings: dict, words: list[WordTime], duration: float | None) -> dict[str, float]:
    length = duration if duration is not None else (words[-1].end if words else 1.0)
    if component == "digit-slide":
        return digit_slide_cues(str(settings.get("to_column", "")), words, length)
    if component == "highlight-words":
        return _reveal_cues([str(item) for item in settings.get("emphasis") or []], words, length)
    if component == "label-callout":
        return _reveal_cues(_part_names(list(settings.get("parts") or [])), words, length)
    if component == "path-trace":
        return _reveal_cues([str(step) for step in settings.get("steps") or []], words, length)
    if component == "stroke-diagram":
        return _reveal_cues(_mark_texts(list(settings.get("marks") or [])), words, length)
    if component == "shape-picture":
        labels = [str(settings.get("subject") or "")]
        labels.extend(str(label) for label in settings.get("labels") or [])
        return _reveal_cues(labels, words, length)
    if component == "arrow-link":
        return _reveal_cues(
            [str(settings.get("left") or ""), str(settings.get("relation") or ""), str(settings.get("right") or "")],
            words,
            length,
        )
    if component == "before-after":
        return _reveal_cues(
            [str(settings.get("before_text") or ""), str(settings.get("after_text") or "")],
            words,
            length,
        )
    if component == "code-line":
        return _reveal_cues([str(item) for item in settings.get("focus") or []], words, length)
    if component == "measure":
        phrases = [str(mark) for mark in settings.get("marks") or []]
        caption = str(settings.get("caption") or "").strip()
        if caption:
            phrases.append(caption)
        return _reveal_cues(phrases, words, length)
    return {}


def _mark_texts(marks: list) -> list[str]:
    texts = []
    for mark in marks:
        if isinstance(mark, dict):
            texts.append(str(mark.get("text", "")))
        else:
            texts.append(str(mark))
    return texts
