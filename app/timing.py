"""Character alignment to words, and the lesson clock."""

from app.schemas import BeatOut, WordTiming


def round_seconds(value: float) -> float:
    return round(value, 3)


def group_characters_into_words(alignment: dict) -> list[WordTiming]:
    """A word runs from its first character's start to its last character's end.

    Spaces separate words. Punctuation stays on the word it is attached to.
    """
    characters = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not isinstance(characters, list) or not isinstance(starts, list) or not isinstance(ends, list):
        raise ValueError("alignment is missing character timings")
    if not characters or not (len(characters) == len(starts) == len(ends)):
        raise ValueError("alignment character timings do not line up")

    words: list[WordTiming] = []
    buffer: list[tuple[str, float, float]] = []

    def close_word() -> None:
        if not buffer:
            return
        words.append(
            WordTiming(
                word="".join(char for char, _, _ in buffer),
                start=buffer[0][1],
                end=buffer[-1][2],
            )
        )
        buffer.clear()

    for char, start, end in zip(characters, starts, ends):
        if not isinstance(char, str) or start is None or end is None:
            raise ValueError("alignment contains a character without a start and end time")
        if char == "" or char.isspace():
            close_word()
            continue
        buffer.append((char, float(start), float(end)))
    close_word()

    if not words:
        raise ValueError("alignment contained no words")
    return words


def build_timeline(
    rendered: list[tuple[str, str, list[WordTiming], bool]],
    padding_seconds: float,
    checkpoint_pause_seconds: float,
) -> tuple[list[BeatOut], float]:
    """Place beats on one lesson clock.

    Duration is the last word's end plus padding. It is not the sum of the
    word lengths, because that sum leaves out the gaps between words.
    A checkpoint adds pause_after after the beat, and the next beat starts
    after that pause. The final cursor is the lesson's total duration.
    """
    cursor = 0.0
    beats: list[BeatOut] = []
    for beat_id, audio_file, words, checkpoint in rendered:
        word_times = [
            WordTiming(word=word.word, start=round_seconds(word.start), end=round_seconds(word.end))
            for word in words
        ]
        duration = round_seconds(word_times[-1].end + padding_seconds)
        start = round_seconds(cursor)
        end = round_seconds(start + duration)
        pause_after = round_seconds(checkpoint_pause_seconds) if checkpoint else None
        beats.append(
            BeatOut(
                id=beat_id,
                audio_file=audio_file,
                start=start,
                duration=duration,
                end=end,
                words=word_times,
                pause_after=pause_after,
            )
        )
        cursor = end + (pause_after or 0.0)
    return beats, round_seconds(cursor)
