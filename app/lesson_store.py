"""Save and list studiolesson rows for one owner id."""

import uuid
from datetime import datetime
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
    def create(self, owner_id: str, topic: str, beats: list[dict[str, Any]]) -> LessonRecord: ...

    def list_for_owner(self, owner_id: str) -> list[LessonRecord]: ...

    def get_for_owner(self, owner_id: str, lesson_id: uuid.UUID) -> LessonRecord | None: ...


class SqlLessonStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, owner_id: str, topic: str, beats: list[dict[str, Any]]) -> LessonRecord:
        row = StudioLesson(owner_id=owner_id, topic=topic, status="draft", beats=beats)
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
