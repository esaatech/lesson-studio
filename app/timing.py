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


_MPEG1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
_MPEG2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_SAMPLE_RATES = {
    3: (44100, 48000, 32000),
    2: (22050, 24000, 16000),
    0: (11025, 12000, 8000),
}


def mp3_seconds(data: bytes) -> float | None:
    """How long an MP3 recording lasts. None when the bytes are not an MP3."""
    offset = 0
    if len(data) >= 10 and data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        offset = 10 + size + (10 if data[5] & 0x10 else 0)
    duration = 0.0
    frames = 0
    limit = len(data)
    while offset + 4 <= limit and frames < 20000:
        if data[offset] != 0xFF or data[offset + 1] & 0xE0 != 0xE0:
            offset += 1
            continue
        header = int.from_bytes(data[offset : offset + 4], "big")
        version = (header >> 19) & 0x3
        layer = (header >> 17) & 0x3
        bitrate_index = (header >> 12) & 0xF
        sample_index = (header >> 10) & 0x3
        padding = (header >> 9) & 0x1
        if version == 1 or layer != 1 or bitrate_index in (0, 15) or sample_index == 3:
            offset += 1
            continue
        bitrate = (_MPEG1_L3 if version == 3 else _MPEG2_L3)[bitrate_index] * 1000
        sample_rate = _SAMPLE_RATES[version][sample_index]
        samples = 1152 if version == 3 else 576
        coefficient = 144 if version == 3 else 72
        frame_length = coefficient * bitrate // sample_rate + padding
        if frame_length < 4 or offset + frame_length > limit:
            break
        duration += samples / sample_rate
        frames += 1
        offset += frame_length
    if frames == 0:
        return None
    return duration


def build_timeline(
    rendered: list[tuple[str, str, list[WordTiming], float]],
) -> tuple[list[BeatOut], float]:
    """Place beats on one lesson clock.

    A beat lasts as long as its recording. Word times stay inside that
    recording. The next beat starts when the recording ends.
    """
    cursor = 0.0
    beats: list[BeatOut] = []
    for beat_id, audio_file, words, recording in rendered:
        word_times = [
            WordTiming(word=word.word, start=round_seconds(word.start), end=round_seconds(word.end))
            for word in words
        ]
        duration = round_seconds(max(recording, word_times[-1].end))
        start = round_seconds(cursor)
        end = round_seconds(start + duration)
        beats.append(
            BeatOut(
                id=beat_id,
                audio_file=audio_file,
                start=start,
                duration=duration,
                end=end,
                words=word_times,
                pause_after=None,
            )
        )
        cursor = end
    return beats, round_seconds(cursor)
