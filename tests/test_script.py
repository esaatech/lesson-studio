import uuid

import pytest
from fastapi.testclient import TestClient

from app.ai_client import AIError
from app.config import get_settings
from app.lesson_routes import get_lesson_store, require_owner
from app.main import app
from tests.test_lessons import MemoryLessonStore

BEAT = {
    "id": "b1",
    "text": "Five sits in the ones place.",
    "kind": "wording",
    "visual": "Digit 5 in the ones column.",
    "checkpoint": False,
}


@pytest.fixture
def lesson_client():
    store = MemoryLessonStore()
    app.dependency_overrides[require_owner] = lambda: "teacher-a"
    app.dependency_overrides[get_lesson_store] = lambda: store
    yield TestClient(app), store
    app.dependency_overrides.clear()


def test_topic_is_written_as_beats_before_audio(monkeypatch, lesson_client):
    client, store = lesson_client

    async def fake_draft(topic: str) -> list[dict]:
        assert topic == "Place value"
        return [BEAT]

    monkeypatch.setattr("app.script_service.draft_beats", fake_draft)

    response = client.post("/v1/lessons", json={"topic": "Place value"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["beats"] == [BEAT]
    assert store.get_for_owner("teacher-a", uuid.UUID(body["id"])).beats == [BEAT]


def test_configured_queue_returns_before_the_model_runs(monkeypatch, lesson_client):
    client, _store = lesson_client
    monkeypatch.setenv("CLOUD_TASKS_QUEUE", "studio-script")
    monkeypatch.setenv("CLOUD_TASKS_PROJECT", "esaasolution")
    monkeypatch.setenv("CLOUD_TASKS_TARGET_URL", "https://studio.example/internal/lessons/script")
    monkeypatch.setenv("CLOUD_TASKS_SERVICE_ACCOUNT", "tasks@example.iam.gserviceaccount.com")
    get_settings.cache_clear()
    called = {}

    def fake_enqueue(lesson_id):
        called["id"] = lesson_id
        return "studio-script"

    async def fake_draft(_topic: str) -> list[dict]:
        raise AssertionError("the model should wait for Cloud Tasks")

    monkeypatch.setattr("app.script_service.enqueue_script", fake_enqueue)
    monkeypatch.setattr("app.script_service.draft_beats", fake_draft)

    response = client.post("/v1/lessons", json={"topic": "Place value"})

    assert response.status_code == 201
    assert response.json()["status"] == "drafting"
    assert response.json()["beats"] == []
    assert str(called["id"]) == response.json()["id"]
    get_settings.cache_clear()


def test_failed_script_stays_on_the_lesson(monkeypatch, lesson_client):
    client, store = lesson_client

    async def fake_draft(_topic: str) -> list[dict]:
        raise AIError("DEEPSEEK_API_KEY is not set")

    monkeypatch.setattr("app.script_service.draft_beats", fake_draft)

    response = client.post("/v1/lessons", json={"topic": "Place value"})

    assert response.status_code == 502
    assert store.rows[0].status == "draft_failed"
    assert str(store.rows[0].id) == response.json()["id"]


def test_queue_worker_saves_beats_for_a_drafting_lesson(monkeypatch, lesson_client):
    _client, store = lesson_client
    lesson = store.create("teacher-a", "Place value", [], status="drafting")

    async def fake_draft(_topic: str) -> list[dict]:
        return [BEAT]

    monkeypatch.setattr("app.lesson_routes.verify_worker", lambda _authorization, _retry: 0)
    monkeypatch.setattr("app.script_service.draft_beats", fake_draft)
    client = TestClient(app)

    response = client.post(
        "/internal/lessons/script",
        json={"lesson_id": str(lesson.id)},
        headers={"Authorization": "Bearer task"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert store.get(lesson.id).beats == [BEAT]


def test_queue_worker_rejects_a_missing_token(lesson_client):
    client, store = lesson_client
    lesson = store.create("teacher-a", "Place value", [], status="drafting")

    response = client.post("/internal/lessons/script", json={"lesson_id": str(lesson.id)})

    assert response.status_code == 403
    assert store.get(lesson.id).status == "drafting"


def test_a_script_may_have_one_hundred_short_lines():
    from pydantic import ValidationError

    from app.script_draft import DraftScript

    beats = [
        {"id": f"b{i}", "text": f"Line {i} is one breath.", "kind": "concept", "visual": "One picture.", "checkpoint": False}
        for i in range(1, 101)
    ]
    script = DraftScript(beats=beats)
    assert len(script.beats) == 100

    try:
        DraftScript(beats=[*beats, {"id": "b101", "text": "One more.", "visual": "One picture."}])
    except ValidationError:
        return
    raise AssertionError("expected more than 100 lines to be rejected")


def test_one_line_cannot_pack_a_paragraph():
    from pydantic import ValidationError

    from app.script_draft import DraftBeat

    try:
        DraftBeat(id="b1", text="x" * 221, kind="concept", visual="One picture.")
    except ValidationError:
        return
    raise AssertionError("expected a 221 character line to be rejected")


def test_each_named_section_may_open_with_an_intro():
    from app.script_draft import DraftScript

    script = DraftScript(
        beats=[
            {"id": "b1", "text": "Welcome to nouns.", "kind": "intro", "visual": "Title Nouns."},
            {"id": "b2", "text": "A noun names a person, place, thing, or idea.", "kind": "concept", "visual": "Person, place, thing, idea."},
            {"id": "b3", "text": "Common nouns.", "kind": "intro", "visual": "Title Common nouns."},
            {"id": "b4", "text": "A common noun names any one of its kind.", "kind": "concept", "visual": "Any girl, any city."},
            {"id": "b5", "text": "Proper nouns.", "kind": "intro", "visual": "Title Proper nouns."},
        ]
    )
    assert [beat.kind for beat in script.beats] == ["intro", "concept", "intro", "concept", "intro"]
