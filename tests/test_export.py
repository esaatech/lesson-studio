from app.export.timeline import audio_graph, frame_times


BEATS = [
    {"id": "s05-a", "audio_file": "s05-a.mp3", "start": 0.0, "end": 3.076, "pause_after": 0.0},
    {"id": "s05-c", "audio_file": "s05-c.mp3", "start": 3.076, "end": 8.567, "pause_after": 0.0},
    {
        "id": "s05-checkpoint",
        "audio_file": "s05-checkpoint.mp3",
        "start": 8.567,
        "end": 10.296,
        "pause_after": 2.0,
    },
]


def test_frames_cover_the_checkpoint_pause():
    times = frame_times(12.296, 30)

    assert len(times) == 369
    assert times[0] == 0
    assert times[-1] < 12.296
    assert any(time >= 10.296 for time in times)


def test_audio_starts_line_up_with_the_lesson_clock(tmp_path):
    graph = audio_graph(BEATS, 12.3, tmp_path)

    assert graph.delays_ms == [0, 3076, 8567]
    assert "adelay=3076:all=1" in graph.filter
    assert "adelay=8567:all=1" in graph.filter
    assert "apad=whole_dur=12.300" in graph.filter
    assert "normalize=0" in graph.filter
    assert [path.name for path in graph.inputs] == ["s05-a.mp3", "s05-c.mp3", "s05-checkpoint.mp3"]
