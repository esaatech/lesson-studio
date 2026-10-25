"""Lesson routes. The owner id comes from the sign-in token, never from the body."""

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import owner_id_from_authorization
from app.db import get_session
from app.lesson_store import LessonCreate, LessonRecord, LessonStore, SqlLessonStore
from app.script_queue import CloudTaskError, verify_worker
from app.script_service import ScriptFailed, run_queued_script, write_script

router = APIRouter()


def require_owner(authorization: str = Header(default="")) -> str:
    return owner_id_from_authorization(authorization)


def get_lesson_store(session: Session = Depends(get_session)) -> LessonStore:
    return SqlLessonStore(session)


@router.post("/v1/lessons", response_model=LessonRecord, status_code=201)
async def create_lesson(
    body: LessonCreate,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord | JSONResponse:
    status = "draft" if body.beats else "drafting"
    lesson = store.create(owner_id, body.topic, body.beats, status)
    if body.beats:
        return lesson
    return await _finish_script(store, lesson)


@router.post("/v1/lessons/{lesson_id}/script", response_model=LessonRecord)
async def rewrite_script(
    lesson_id: uuid.UUID,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    if lesson is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    if lesson.status == "drafting":
        return JSONResponse(status_code=409, content={"error": "Script is already being written."})
    marked = store.mark_status(lesson_id, "drafting")
    if marked is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    return await _finish_script(store, marked)


class ScriptTask(BaseModel):
    lesson_id: uuid.UUID


@router.post("/internal/lessons/script")
async def draft_from_queue(
    body: ScriptTask,
    authorization: str = Header(default=""),
    x_cloudtasks_taskretrycount: str = Header(default="0"),
    store: LessonStore = Depends(get_lesson_store),
) -> JSONResponse:
    try:
        retry_count = verify_worker(authorization, x_cloudtasks_taskretrycount)
    except CloudTaskError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
    status_code, payload = await run_queued_script(store, body.lesson_id, retry_count)
    return JSONResponse(status_code=status_code, content=payload)


async def _finish_script(store: LessonStore, lesson: LessonRecord) -> LessonRecord | JSONResponse:
    try:
        return await write_script(store, lesson)
    except ScriptFailed as exc:
        return JSONResponse(status_code=502, content={"error": exc.message, "id": str(exc.lesson_id)})
    except CloudTaskError as exc:
        store.mark_status(lesson.id, "draft_failed")
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message, "id": str(lesson.id)})


@router.get("/v1/lessons", response_model=list[LessonRecord])
def list_lessons(
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> list[LessonRecord]:
    return store.list_for_owner(owner_id)


class BeatUpdate(BaseModel):
    text: str
    visual: str = ""
    checkpoint: bool = False

    @field_validator("text")
    @classmethod
    def spoken_line_is_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Spoken line is required")
        return cleaned


@router.patch("/v1/lessons/{lesson_id}/beats/{beat_id}", response_model=LessonRecord)
def update_beat(
    lesson_id: uuid.UUID,
    beat_id: str,
    body: BeatUpdate,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    if lesson is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    saved = store.update_beat(lesson_id, beat_id, body.text, body.visual.strip(), body.checkpoint)
    if saved is None:
        return JSONResponse(status_code=404, content={"error": "Line not found"})
    return saved


@router.get("/v1/lessons/{lesson_id}", response_model=LessonRecord)
def read_lesson(
    lesson_id: uuid.UUID,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    if lesson is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    return lesson
