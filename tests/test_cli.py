import json

from app.cli import main
from app.elevenlabs import ElevenLabsError
from app.schemas import BeatOut, LessonAudioResponse, WordTiming


def test_audio_command_prints_timings(tmp_path, capsys, monkeypatch):
    request_path = tmp_path / "beats.json"
    request_path.write_text(json.dumps({"beats": [{"id": "s05-a", "text": "Here is five."}]}))

    async def fake_render(request, settings=None):
        return LessonAudioResponse(
            request_id="abc",
            output_dir="output/abc",
            beats=[
                BeatOut(
                    id="s05-a",
                    audio_file="s05-a.mp3",
                    start=0.0,
                    duration=1.15,
                    end=1.15,
                    words=[WordTiming(word="Here", start=0.0, end=1.0)],
                )
            ],
            total_duration=1.15,
        )

    monkeypatch.setattr("app.cli.render_lesson_audio", fake_render)

    assert main(["audio", str(request_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["beats"][0]["audio_file"] == "s05-a.mp3"
    assert printed["total_duration"] == 1.15


def test_missing_request_file(capsys):
    assert main(["audio", "missing-beats.json"]) == 1
    assert "not found" in capsys.readouterr().err


def test_elevenlabs_error_is_a_message(tmp_path, capsys, monkeypatch):
    request_path = tmp_path / "beats.json"
    request_path.write_text(json.dumps({"beats": [{"id": "s05-a", "text": "Here is five."}]}))

    async def fail(request, settings=None):
        raise ElevenLabsError(401, "Invalid ElevenLabs API key: rejected", beat_id="s05-a")

    monkeypatch.setattr("app.cli.render_lesson_audio", fail)

    assert main(["audio", str(request_path)]) == 1
    error_output = capsys.readouterr().err
    assert "Invalid ElevenLabs API key: rejected" in error_output
    assert "s05-a" in error_output
