import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import get_settings
from app.lesson_routes import get_lesson_store, require_owner
from app.lesson_store import LessonRecord
from app.main import app
from app.models import StudioLesson


class MemoryLessonStore:
    def __init__(self) -> None:
        self.rows: list[LessonRecord] = []

    def create(self, owner_id: str, topic: str, beats: list[dict], status: str = "draft") -> LessonRecord:
        now = datetime.now(timezone.utc)
        record = LessonRecord(
            id=uuid.uuid4(),
            owner_id=owner_id,
            topic=topic,
            status=status,
            beats=beats,
            audio_dir="",
            html_file="",
            mp4_file="",
            created_at=now,
            updated_at=now,
        )
        self.rows.append(record)
        return record

    def get(self, lesson_id: uuid.UUID) -> LessonRecord | None:
        for row in self.rows:
            if row.id == lesson_id:
                return row
        return None

    def save_script(self, lesson_id: uuid.UUID, beats: list[dict]) -> LessonRecord | None:
        return self._replace(lesson_id, beats=beats, status="draft")

    def update_beat(
        self, lesson_id: uuid.UUID, beat_id: str, text: str, visual: str, checkpoint: bool
    ) -> LessonRecord | None:
        current = self.get(lesson_id)
        if current is None:
            return None
        beats = []
        found = False
        for beat in current.beats:
            if str(beat.get("id")) != beat_id:
                beats.append(beat)
                continue
            found = True
            beats.append({**beat, "text": text, "visual": visual, "checkpoint": checkpoint})
        if not found:
            return None
        return self._replace(lesson_id, beats=beats)

    def mark_status(self, lesson_id: uuid.UUID, status: str) -> LessonRecord | None:
        return self._replace(lesson_id, status=status)

    def save_render(
        self, lesson_id: uuid.UUID, beats: list[dict], audio_dir: str, html_file: str
    ) -> LessonRecord | None:
        return self._replace(lesson_id, beats=beats, audio_dir=audio_dir, html_file=html_file, status="rendered")

    def _replace(self, lesson_id: uuid.UUID, **changes) -> LessonRecord | None:
        current = self.get(lesson_id)
        if current is None:
            return None
        updated = current.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
        self.rows = [updated if row.id == lesson_id else row for row in self.rows]
        return updated

    def list_for_owner(self, owner_id: str) -> list[LessonRecord]:
        return [row for row in reversed(self.rows) if row.owner_id == owner_id]

    def get_for_owner(self, owner_id: str, lesson_id: uuid.UUID) -> LessonRecord | None:
        for row in self.rows:
            if row.id == lesson_id and row.owner_id == owner_id:
                return row
        return None


def test_table_name_is_studiolesson():
    assert StudioLesson.__tablename__ == "studiolesson"
    assert "owner_id" in StudioLesson.__table__.columns


def test_lesson_is_saved_for_the_token_owner():
    store = MemoryLessonStore()
    app.dependency_overrides[require_owner] = lambda: "teacher-a"
    app.dependency_overrides[get_lesson_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post(
            "/v1/lessons",
            json={
                "topic": "Place value",
                "owner_id": "someone-else",
                "beats": [{"id": "s05-a", "text": "Here is five.", "visual": "The digit 5."}],
            },
        )
        listed = client.get("/v1/lessons")
        assert created.status_code == 201
        assert created.json()["owner_id"] == "teacher-a"
        assert created.json()["topic"] == "Place value"
        assert created.json()["status"] == "draft"
        assert [lesson["id"] for lesson in listed.json()] == [created.json()["id"]]
    finally:
        app.dependency_overrides.clear()


def test_owner_can_edit_one_line():
    store = MemoryLessonStore()
    app.dependency_overrides[require_owner] = lambda: "teacher-a"
    app.dependency_overrides[get_lesson_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post(
            "/v1/lessons",
            json={
                "topic": "CSS",
                "beats": [{"id": "line-1", "text": "Plain text.", "visual": "A white page.", "checkpoint": False}],
            },
        )
        lesson_id = created.json()["id"]
        saved = client.patch(
            f"/v1/lessons/{lesson_id}/beats/line-1",
            json={"text": "Styled text.", "visual": "A blue heading.", "checkpoint": True},
        )
        assert saved.status_code == 200
        beat = saved.json()["beats"][0]
        assert beat["text"] == "Styled text."
        assert beat["visual"] == "A blue heading."
        assert beat["checkpoint"] is True
    finally:
        app.dependency_overrides.clear()


def test_another_owner_cannot_open_the_lesson():
    store = MemoryLessonStore()
    saved = store.create("teacher-a", "Place value", [])
    app.dependency_overrides[require_owner] = lambda: "teacher-b"
    app.dependency_overrides[get_lesson_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.get(f"/v1/lessons/{saved.id}")
        assert response.status_code == 404
        assert response.json() == {"error": "Lesson not found"}
        assert client.get("/v1/lessons").json() == []
    finally:
        app.dependency_overrides.clear()


def test_missing_token_is_rejected():
    client = TestClient(app)
    response = client.post("/v1/lessons", json={"topic": "Place value"})
    assert response.status_code == 401
    assert response.json() == {"error": "Sign in is required"}


def test_firebase_project_must_be_configured(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/v1/lessons", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 500
    assert response.json() == {"error": "FIREBASE_PROJECT_ID is not set"}
    get_settings.cache_clear()
