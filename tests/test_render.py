from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.lesson_routes import get_lesson_store, require_owner
from app.main import app
from app.schemas import BeatOut, LessonAudioResponse, WordTiming
from tests.test_lessons import MemoryLessonStore

BEAT = {"id": "b1", "text": "Five sits in the ones place.", "visual": "Digit 5 in the ones column.", "checkpoint": False}


def _client():
    store = MemoryLessonStore()
    app.dependency_overrides[require_owner] = lambda: "teacher-a"
    app.dependency_overrides[get_lesson_store] = lambda: store
    return TestClient(app), store


def _ready(store: MemoryLessonStore):
    return store.create("teacher-a", "Place value", [BEAT], status="draft")


def test_approve_uses_the_render_queue_and_not_the_script_queue(monkeypatch):
    client, store = _client()
    lesson = _ready(store)
    monkeypatch.setenv("CLOUD_TASKS_QUEUE", "studio-script")
    monkeypatch.setenv("CLOUD_TASKS_RENDER_QUEUE", "studio-render")
    monkeypatch.setenv("CLOUD_TASKS_PROJECT", "esaasolution")
    monkeypatch.setenv("CLOUD_TASKS_TARGET_URL", "https://studio.example/internal/lessons/script")
    monkeypatch.setenv("CLOUD_TASKS_RENDER_TARGET_URL", "https://studio.example/internal/lessons/render")
    monkeypatch.setenv("CLOUD_TASKS_SERVICE_ACCOUNT", "tasks@example.iam.gserviceaccount.com")
    get_settings.cache_clear()
    called = {}

    def fake_enqueue(lesson_id):
        called["id"] = lesson_id
        return "studio-render"

    async def fake_audio(*_args, **_kwargs):
        raise AssertionError("audio waits for the render queue")

    monkeypatch.setattr("app.render_service.enqueue_render", fake_enqueue)
    monkeypatch.setattr("app.render_service.render_lesson_audio", fake_audio)
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/render")
        assert response.status_code == 200
        assert response.json()["status"] == "rendering"
        assert called["id"] == lesson.id
        assert store.get(lesson.id).status == "rendering"
    finally:
        get_settings.cache_clear()
        app.dependency_overrides.clear()


def test_script_queue_alone_still_builds_the_page_in_the_request(monkeypatch, tmp_path):
    client, store = _client()
    lesson = _ready(store)
    monkeypatch.setenv("CLOUD_TASKS_QUEUE", "studio-script")
    monkeypatch.setenv("CLOUD_TASKS_PROJECT", "esaasolution")
    monkeypatch.setenv("CLOUD_TASKS_TARGET_URL", "https://studio.example/internal/lessons/script")
    monkeypatch.setenv("CLOUD_TASKS_SERVICE_ACCOUNT", "tasks@example.iam.gserviceaccount.com")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    _patch_builders(monkeypatch, tmp_path)
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/render")
        assert response.status_code == 200
        assert response.json()["status"] == "rendered"
        assert response.json()["beats"][0]["text"] == BEAT["text"]
        assert response.json()["beats"][0]["component"] == "label-callout"
        page = client.get(f"/v1/lessons/{lesson.id}/page")
        audio = client.get(f"/v1/lessons/{lesson.id}/media/b1.mp3")
        assert page.status_code == 200
        assert "Play" in page.text
        assert audio.status_code == 200
        assert audio.content == b"mp3"
    finally:
        get_settings.cache_clear()
        app.dependency_overrides.clear()


def test_approve_rejects_a_script_that_is_still_being_written():
    client, store = _client()
    lesson = store.create("teacher-a", "Place value", [BEAT], status="drafting")
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/render")
        assert response.status_code == 409
        assert store.get(lesson.id).status == "drafting"
    finally:
        app.dependency_overrides.clear()


def test_approve_rejects_a_line_with_no_picture_description():
    client, store = _client()
    lesson = store.create("teacher-a", "Place value", [{**BEAT, "visual": ""}], status="draft")
    try:
        response = client.post(f"/v1/lessons/{lesson.id}/render")
        assert response.status_code == 400
        assert store.get(lesson.id).status == "draft"
    finally:
        app.dependency_overrides.clear()


def test_render_worker_saves_the_page_for_a_rendering_lesson(monkeypatch):
    client, store = _client()
    lesson = store.create("teacher-a", "Place value", [BEAT], status="rendering")

    async def fake_compose(store, current):
        return store.save_render(current.id, current.beats, "audio", "page.html")

    monkeypatch.setattr("app.lesson_routes.verify_worker", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr("app.render_service.compose_lesson", fake_compose)
    try:
        response = client.post(
            "/internal/lessons/render",
            json={"lesson_id": str(lesson.id)},
            headers={"Authorization": "Bearer task"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rendered"
        assert store.get(lesson.id).html_file == "page.html"
    finally:
        app.dependency_overrides.clear()


def test_render_worker_rejects_a_missing_token():
    client, store = _client()
    lesson = store.create("teacher-a", "Place value", [BEAT], status="rendering")
    try:
        response = client.post("/internal/lessons/render", json={"lesson_id": str(lesson.id)})
        assert response.status_code == 403
        assert store.get(lesson.id).status == "rendering"
    finally:
        app.dependency_overrides.clear()


def _patch_builders(monkeypatch, tmp_path: Path) -> None:
    spoken = tmp_path / "spoken"
    spoken.mkdir()
    (spoken / "b1.mp3").write_bytes(b"mp3")

    async def fake_audio(_request, settings=None):
        return LessonAudioResponse(
            request_id="req",
            output_dir=str(spoken),
            beats=[
                BeatOut(
                    id="b1",
                    audio_file="b1.mp3",
                    start=0,
                    duration=1.2,
                    end=1.2,
                    words=[WordTiming(word="Five", start=0, end=0.4)],
                    pause_after=None,
                )
            ],
            total_duration=1.2,
        )

    async def fake_build(payload, output_dir=None):
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        page = directory / "index.html"
        page.write_text("<html>Play</html>")
        return {
            "html_file": str(page),
            "beats": [{"id": "b1", "component": "label-callout", "start": 0, "end": 1.2, "pause_after": 0}],
        }

    monkeypatch.setattr("app.render_service.render_lesson_audio", fake_audio)
    monkeypatch.setattr("app.render_service.build_lesson", fake_build)
