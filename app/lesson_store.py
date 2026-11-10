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


def layout_with_piece(beat: dict[str, Any], piece: str, x: float, y: float) -> dict[str, Any]:
    layout = dict(beat.get("layout") or {}) if isinstance(beat.get("layout"), dict) else {}
    pieces = dict(layout.get("pieces") or {}) if isinstance(layout.get("pieces"), dict) else {}
    pieces[piece] = {"x": float(x), "y": float(y)}
    layout["pieces"] = pieces
    return {**beat, "layout": layout}


def new_beat_id(beats: list[dict[str, Any]]) -> str:
    taken = {str(beat.get("id") or "") for beat in beats}
    for _ in range(8):
        candidate = f"b{uuid.uuid4().hex[:10]}"
        if candidate not in taken:
            return candidate
    return f"b{uuid.uuid4().hex}"


def insert_beat_after(
    beats: list[dict[str, Any]], after_id: str | None, beat: dict[str, Any]
) -> list[dict[str, Any]] | None:
    if not after_id:
        return [*beats, beat]
    placed: list[dict[str, Any]] = []
    found = False
    for item in beats:
        placed.append(item)
        if str(item.get("id")) == after_id:
            placed.append(beat)
            found = True
    if not found:
        return None
    return placed


def retime_beats(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cursor = 0.0
    placed: list[dict[str, Any]] = []
    for beat in beats:
        duration = float(beat.get("duration") or 0)
        if duration <= 0:
            duration = max(0.0, float(beat.get("end") or 0) - float(beat.get("start") or 0))
        start = round(cursor, 3)
        end = round(start + duration, 3)
        placed.append({**beat, "start": start, "end": end, "pause_after": 0.0, "duration": duration})
        cursor = end
    return placed


def copy_layout(layout: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(layout, dict):
        return {}
    pieces: dict[str, dict[str, float]] = {}
    raw_pieces = layout.get("pieces")
    if isinstance(raw_pieces, dict):
        for key, value in raw_pieces.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            pieces[key] = {"x": float(value.get("x") or 0), "y": float(value.get("y") or 0)}
    return {"pieces": pieces} if pieces else {}


class LessonStore(Protocol):
    def create(self, owner_id: str, topic: str, beats: list[dict[str, Any]], status: str = "draft") -> LessonRecord: ...

    def list_for_owner(self, owner_id: str) -> list[LessonRecord]: ...

    def get_for_owner(self, owner_id: str, lesson_id: uuid.UUID) -> LessonRecord | None: ...

    def get(self, lesson_id: uuid.UUID) -> LessonRecord | None: ...

    def save_script(self, lesson_id: uuid.UUID, beats: list[dict[str, Any]]) -> LessonRecord | None: ...

    def save_beats(self, lesson_id: uuid.UUID, beats: list[dict[str, Any]]) -> LessonRecord | None: ...

    def update_beat(
        self, lesson_id: uuid.UUID, beat_id: str, text: str, visual: str, kind: str, checkpoint: bool
    ) -> LessonRecord | None: ...

    def update_beat_layout(
        self, lesson_id: uuid.UUID, beat_id: str, piece: str, x: float, y: float
    ) -> LessonRecord | None: ...

    def delete_beat(self, lesson_id: uuid.UUID, beat_id: str) -> LessonRecord | None: ...

    def mark_status(self, lesson_id: uuid.UUID, status: str) -> LessonRecord | None: ...

    def save_render(
        self, lesson_id: uuid.UUID, beats: list[dict[str, Any]], audio_dir: str, html_file: str
    ) -> LessonRecord | None: ...

    def save_export(self, lesson_id: uuid.UUID, mp4_file: str) -> LessonRecord | None: ...

    def commit(self) -> None: ...


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

    def save_beats(self, lesson_id: uuid.UUID, beats: list[dict[str, Any]]) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        row.beats = list(beats)
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def update_beat(
        self, lesson_id: uuid.UUID, beat_id: str, text: str, visual: str, kind: str, checkpoint: bool
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
            updated = {**beat, "text": text, "visual": visual, "kind": kind, "checkpoint": checkpoint}
            updated.pop("component", None)
            updated.pop("settings", None)
            beats.append(updated)
        if not found:
            return None
        row.beats = beats
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def update_beat_layout(
        self, lesson_id: uuid.UUID, beat_id: str, piece: str, x: float, y: float
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
            beats.append(layout_with_piece(beat, piece, x, y))
        if not found:
            return None
        row.beats = beats
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def delete_beat(self, lesson_id: uuid.UUID, beat_id: str) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        remaining = [beat for beat in list(row.beats or []) if str(beat.get("id")) != beat_id]
        if len(remaining) == len(list(row.beats or [])):
            return None
        if not remaining:
            return None
        row.beats = retime_beats(remaining)
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

    def save_export(self, lesson_id: uuid.UUID, mp4_file: str) -> LessonRecord | None:
        row = self._session.get(StudioLesson, lesson_id)
        if row is None:
            return None
        row.mp4_file = mp4_file
        row.status = "exported"
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return LessonRecord.model_validate(row)

    def commit(self) -> None:
        self._session.commit()
