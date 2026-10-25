from app.schemas import WordTiming
from app.timing import build_timeline, group_characters_into_words


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


def test_duration_uses_last_word_end_plus_padding_not_the_sum():
    words = [
        WordTiming(word="Here", start=0.0, end=0.40),
        WordTiming(word="five", start=1.10, end=4.923),
    ]

    beats, total = build_timeline([("s05-a", "s05-a.mp3", words, False)], padding_seconds=0.15, checkpoint_pause_seconds=2.0)

    summed = (0.40 - 0.0) + (4.923 - 1.10)
    assert beats[0].duration == 5.073
    assert beats[0].duration != round(summed + 0.15, 3)
    assert beats[0].start == 0.0
    assert beats[0].end == 5.073
    assert total == 5.073
    assert beats[0].pause_after is None


def test_checkpoint_pause_shifts_the_following_beat_and_the_total():
    first = [WordTiming(word="Here", start=0.0, end=2.85)]
    checkpoint = [WordTiming(word="Sense", start=0.0, end=1.05)]
    after = [WordTiming(word="Next", start=0.0, end=4.92)]

    beats, total = build_timeline(
        [
            ("s05-a", "s05-a.mp3", first, False),
            ("s05-checkpoint", "s05-checkpoint.mp3", checkpoint, True),
            ("s05-c", "s05-c.mp3", after, False),
        ],
        padding_seconds=0.15,
        checkpoint_pause_seconds=2.0,
    )

    assert beats[0].start == 0.0
    assert beats[0].end == 3.0
    assert beats[1].start == 3.0
    assert beats[1].duration == 1.2
    assert beats[1].end == 4.2
    assert beats[1].pause_after == 2.0
    assert beats[2].start == 6.2
    assert beats[2].end == 11.27
    assert total == 11.27


def test_pause_after_the_last_beat_is_part_of_the_total():
    words = [WordTiming(word="Check", start=0.0, end=0.85)]

    beats, total = build_timeline(
        [("s05-checkpoint", "s05-checkpoint.mp3", words, True)],
        padding_seconds=0.15,
        checkpoint_pause_seconds=2.0,
    )

    assert beats[0].end == 1.0
    assert beats[0].pause_after == 2.0
    assert total == 3.0
