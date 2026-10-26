import asyncio
import json
from pathlib import Path

from app.export.render import export_lesson


def test_export_records_the_saved_page_without_rewriting_it(tmp_path, monkeypatch):
    saved = "<html><body>saved-page</body></html>"
    (tmp_path / "index.html").write_text(saved)
    (tmp_path / "b1.mp3").write_bytes(b"audio")
    (tmp_path / "lesson.json").write_text(
        json.dumps(
            {
                "id": "lesson",
                "total_duration": 1.0,
                "beats": [{"id": "b1", "start": 0.0, "end": 1.0, "audio_file": "b1.mp3", "pause_after": 0}],
            }
        )
    )
    seen = {}

    async def capture(page_path, _times, folder):
        seen["page"] = Path(page_path).read_text()
        (folder / "frame_0000.png").write_bytes(b"png")

    def ffmpeg(command, _failure):
        Path(command[-1]).write_bytes(b"out")

    monkeypatch.setattr("app.export.render.shutil.which", lambda _name: "ffmpeg")
    monkeypatch.setattr("app.export.render._capture_frames", capture)
    monkeypatch.setattr("app.export.render._run_ffmpeg", ffmpeg)

    asyncio.run(export_lesson(tmp_path, fps=1))

    assert (tmp_path / "index.html").read_text() == saved
    assert seen["page"] == saved
