from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.export.render import ExportError
from app.lesson_routes import get_lesson_store, require_owner
from app.main import app
from tests.test_lessons import MemoryLessonStore

BEAT = {"id": "b1", "text": "Welcome.", "visual": "A welcome line.", "checkpoint": False}


def _client():
    store = MemoryLessonStore()
    app.dependency_overrides[require_owner] = lambda: "teacher-a"
    app.dependency_overrides[get_lesson_store] = lambda: store
    return TestClient(app), store


def _rendered(store: MemoryLessonStore, directory: Path):
    lesson = store.create("teacher-a", "Lesson: Welcome", [BEAT], status="rendered")
    page = directory / "index.html"
    page.write_text("<html></html>")
    return store.save_render(lesson.id, [BEAT], str(directory), str(page))


def test_export_saves_the_video_for_download(monkeypatch, tmp_path):
    client, store = _client()
    lesson = _rendered(store, tmp_path)
    video = tmp_path / f"{lesson.id}.mp4"
    video.write_bytes(b"mp4")

    async def fake_export(directory, fps=30):
        assert directory == tmp_path
        assert fps == 30
        return {"mp4_file": str(video), "frames": 3, "fps": fps}

    monkeypatch.setattr("app.export_service.export_lesson", fake_export)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/export")
        assert response.status_code == 200
        assert response.json()["status"] == "exported"
        assert response.json()["mp4_file"].endswith(".mp4")
        downloaded = client.get(f"/v1/lessons/{lesson.id}/video")
        assert downloaded.status_code == 200
        assert downloaded.content == b"mp4"
        assert downloaded.headers["content-type"].startswith("video/mp4")
    finally:
        get_settings.cache_clear()
        app.dependency_overrides.clear()


def test_export_waits_until_the_lesson_page_exists():
    client, store = _client()
    lesson = store.create("teacher-a", "Lesson: Welcome", [BEAT], status="draft")
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/export")
        assert response.status_code == 409
        assert store.get(lesson.id).status == "draft"
    finally:
        app.dependency_overrides.clear()


def test_export_failure_can_be_tried_again(monkeypatch, tmp_path):
    client, store = _client()
    lesson = _rendered(store, tmp_path)

    async def fake_export(_directory, fps=30):
        raise ExportError("ffmpeg is not installed.")

    monkeypatch.setattr("app.export_service.export_lesson", fake_export)
    try:
        failed = client.post(f"/v1/lessons/{lesson.id}/export")
        assert failed.status_code == 502
        assert store.get(lesson.id).status == "export_failed"
        again = client.post(f"/v1/lessons/{lesson.id}/export")
        assert again.status_code == 502
    finally:
        app.dependency_overrides.clear()
