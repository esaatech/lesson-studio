"""Save and list studiolesson rows for one owner id."""

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudioLesson


class LessonCreate(BaseModel):
    topic: str
    beats: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("topic")
    @classmethod
    def topic_is_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Topic is required")
        return cleaned


class LessonRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: str
    topic: str
    status: str
    beats: list[dict[str, Any]]
    audio_dir: str
    html_file: str
    mp4_file: str
    created_at: datetime
    updated_at: datetime


class LessonStore(Protocol):
    def create(self, owner_id: str, topic: str, beats: list[dict[str, Any]], status: str = "draft") -> LessonRecord: ...

    def list_for_owner(self, owner_id: str) -> list[LessonRecord]: ...

    def get_for_owner(self, owner_id: str, lesson_id: uuid.UUID) -> LessonRecord | None: ...

    def get(self, lesson_id: uuid.UUID) -> LessonRecord | None: ...

    def save_script(self, lesson_id: uuid.UUID, beats: list[dict[str, Any]]) -> LessonRecord | None: ...

    def update_beat(
        self, lesson_id: uuid.UUID, beat_id: str, text: str, visual: str, checkpoint: bool
    ) -> LessonRecord | None: ...

    def mark_status(self, lesson_id: uuid.UUID, status: str) -> LessonRecord | None: ...

    def save_render(
        self, lesson_id: uuid.UUID, beats: list[dict[str, Any]], audio_dir: str, html_file: str
    ) -> LessonRecord | None: ...


class SqlLessonStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, owner_id: str, topic: str, beats: list[dict[str, Any]], status: str = "draft") -> LessonRecord:
        row = StudioLesson(owner_id=owner_id, topic=topic, status=status, beats=beats)
        self._session.add(row)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def list_for_owner(self, owner_id: str) -> list[LessonRecord]:
        rows = self._session.scalars(
            select(StudioLesson).where(StudioLesson.owner_id == owner_id).order_by(StudioLesson.created_at.desc())
        )
        return [LessonRecord.model_validate(row) for row in rows]

    def get_for_owner(self, owner_id: str, lesson_id: uuid.UUID) -> LessonRecord | None:
        row = self._session.scalar(
            select(StudioLesson).where(StudioLesson.id == lesson_id, StudioLesson.owner_id == owner_id)
        )
        if row is None:
            return None
        return LessonRecord.model_validate(row)

    def get(self, lesson_id: uuid.UUID) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        return LessonRecord.model_validate(row)

    def save_script(self, lesson_id: uuid.UUID, beats: list[dict[str, Any]]) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        row.beats = beats
        row.status = "draft"
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def update_beat(
        self, lesson_id: uuid.UUID, beat_id: str, text: str, visual: str, checkpoint: bool
    ) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        beats = []
        found = False
        for beat in list(row.beats or []):
            if str(beat.get("id")) != beat_id:
                beats.append(beat)
                continue
            found = True
            beats.append({**beat, "text": text, "visual": visual, "checkpoint": checkpoint})
        if not found:
            return None
        row.beats = beats
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def mark_status(self, lesson_id: uuid.UUID, status: str) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def save_render(
        self, lesson_id: uuid.UUID, beats: list[dict[str, Any]], audio_dir: str, html_file: str
    ) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        row.beats = beats
        row.audio_dir = audio_dir
        row.html_file = html_file
        row.status = "rendered"
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)
