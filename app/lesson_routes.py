"""Lesson routes. The owner id comes from the sign-in token, never from the body."""

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import owner_id_from_authorization
from app.db import get_session
from app.lesson_store import LessonCreate, LessonRecord, LessonStore, SqlLessonStore

router = APIRouter()


def require_owner(authorization: str = Header(default="")) -> str:
    return owner_id_from_authorization(authorization)


def get_lesson_store(session: Session = Depends(get_session)) -> LessonStore:
    return SqlLessonStore(session)


@router.post("/v1/lessons", response_model=LessonRecord, status_code=201)
def create_lesson(
    body: LessonCreate,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord:
    return store.create(owner_id, body.topic, body.beats)


@router.get("/v1/lessons", response_model=list[LessonRecord])
def list_lessons(
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> list[LessonRecord]:
    return store.list_for_owner(owner_id)


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
