from app.schemas import WordTiming
from app.timing import build_timeline, group_characters_into_words, mp3_seconds


def test_groups_characters_into_words_and_keeps_punctuation():
    alignment = {
        "characters": list("Move it."),
        "character_start_times_seconds": [0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70],
        "character_end_times_seconds": [0.05, 0.10, 0.20, 0.26, 0.35, 0.48, 0.60, 0.80],
    }

    words = group_characters_into_words(alignment)

    assert [(word.word, word.start, word.end) for word in words] == [
        ("Move", 0.00, 0.26),
        ("it.", 0.40, 0.80),
    ]


def _frame(bitrate_index: int = 9) -> bytes:
    # MPEG1 Layer 3, 128 kbps, 44100 Hz, no padding. One frame is 1152 samples.
    return bytes([0xFF, 0xFB, (bitrate_index << 4), 0xC0]) + bytes(417 - 4)


def test_mp3_duration_is_the_sum_of_its_frames():
    frames = _frame() * 3

    duration = mp3_seconds(frames)

    assert duration is not None
    assert abs(duration - 3 * 1152 / 44100) < 0.0001


def test_duration_is_the_length_of_the_recording():
    words = [
        WordTiming(word="Here", start=0.0, end=0.40),
        WordTiming(word="five", start=1.10, end=4.923),
    ]

    beats, total = build_timeline([("s05-a", "s05-a.mp3", words, 5.40)])

    assert beats[0].duration == 5.4
    assert beats[0].duration > words[-1].end
    assert beats[0].start == 0.0
    assert beats[0].end == 5.4
    assert total == 5.4
    assert beats[0].pause_after is None


def test_a_question_does_not_hold_the_clock_before_the_next_line():
    first = [WordTiming(word="Here", start=0.0, end=2.85)]
    question = [WordTiming(word="Which", start=0.0, end=1.05)]
    after = [WordTiming(word="Next", start=0.0, end=4.92)]

    beats, total = build_timeline(
        [
            ("s05-a", "s05-a.mp3", first, 3.0),
            ("s05-question", "s05-question.mp3", question, 1.2),
            ("s05-c", "s05-c.mp3", after, 5.07),
        ],
    )

    assert beats[0].start == 0.0
    assert beats[0].end == 3.0
    assert beats[1].start == 3.0
    assert beats[1].duration == 1.2
    assert beats[1].end == 4.2
    assert beats[1].pause_after is None
    assert beats[2].start == 4.2
    assert beats[2].end == 9.27
    assert total == 9.27
