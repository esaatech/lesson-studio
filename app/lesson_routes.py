"""Lesson routes. The owner id comes from the sign-in token, never from the body."""

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import owner_id_from_authorization
from app.config import get_settings
from app.db import get_session
from app.lesson_store import LessonCreate, LessonRecord, LessonStore, SqlLessonStore
from app.render_service import RenderFailed, run_queued_render, write_render
from app.script_queue import CloudTaskError, verify_worker
from app.script_service import ScriptFailed, run_queued_script, write_script

_MEDIA_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.mp3$")
_READY_TO_RENDER = {"draft", "render_failed", "rendered"}

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
    if lesson.status == "rendering":
        return JSONResponse(status_code=409, content={"error": "The lesson is being made. Wait until it finishes to edit a line."})
    saved = store.update_beat(lesson_id, beat_id, body.text, body.visual.strip(), body.checkpoint)
    if saved is None:
        return JSONResponse(status_code=404, content={"error": "Line not found"})
    return saved


@router.post("/v1/lessons/{lesson_id}/render", response_model=LessonRecord)
async def render_lesson(
    lesson_id: uuid.UUID,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> LessonRecord | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    if lesson is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    if lesson.status == "rendering":
        return JSONResponse(status_code=409, content={"error": "The lesson is already being made."})
    if lesson.status not in _READY_TO_RENDER:
        return JSONResponse(status_code=409, content={"error": "Approve the script after it is ready."})
    if not lesson.beats:
        return JSONResponse(status_code=400, content={"error": "Generate a script before approving it."})
    if any(not str(beat.get("text") or "").strip() or not str(beat.get("visual") or "").strip() for beat in lesson.beats):
        return JSONResponse(
            status_code=400,
            content={"error": "Each line needs spoken words and an on-screen description."},
        )
    marked = store.mark_status(lesson_id, "rendering")
    if marked is None:
        return JSONResponse(status_code=404, content={"error": "Lesson not found"})
    return await _finish_render(store, marked)


class RenderTask(BaseModel):
    lesson_id: uuid.UUID


@router.post("/internal/lessons/render")
async def render_from_queue(
    body: RenderTask,
    authorization: str = Header(default=""),
    x_cloudtasks_taskretrycount: str = Header(default="0"),
    store: LessonStore = Depends(get_lesson_store),
) -> JSONResponse:
    audience = get_settings().cloud_tasks_render_target_url.strip() or None
    try:
        retry_count = verify_worker(authorization, x_cloudtasks_taskretrycount, audience)
    except CloudTaskError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
    status_code, payload = await run_queued_render(store, body.lesson_id, retry_count)
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/v1/lessons/{lesson_id}/page", response_model=None)
def read_lesson_page(
    lesson_id: uuid.UUID,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> FileResponse | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    path = _owned_output(lesson.html_file if lesson else "")
    if lesson is None or path is None:
        return JSONResponse(status_code=404, content={"error": "The lesson page is not ready."})
    return FileResponse(path, media_type="text/html")


@router.get("/v1/lessons/{lesson_id}/media/{name}", response_model=None)
def read_lesson_media(
    lesson_id: uuid.UUID,
    name: str,
    owner_id: str = Depends(require_owner),
    store: LessonStore = Depends(get_lesson_store),
) -> FileResponse | JSONResponse:
    lesson = store.get_for_owner(owner_id, lesson_id)
    if lesson is None or not _MEDIA_NAME.fullmatch(name):
        return JSONResponse(status_code=404, content={"error": "Audio not found."})
    path = _owned_output(str(Path(lesson.audio_dir) / name))
    if path is None:
        return JSONResponse(status_code=404, content={"error": "Audio not found."})
    return FileResponse(path, media_type="audio/mpeg")


def _owned_output(raw: str) -> Path | None:
    if not raw.strip():
        return None
    root = Path(get_settings().output_dir).resolve()
    path = Path(raw).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        return None
    return path


async def _finish_render(store: LessonStore, lesson: LessonRecord) -> LessonRecord | JSONResponse:
    try:
        return await write_render(store, lesson)
    except RenderFailed as exc:
        return JSONResponse(status_code=502, content={"error": exc.message, "id": str(exc.lesson_id)})
    except CloudTaskError as exc:
        store.mark_status(lesson.id, "render_failed")
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message, "id": str(lesson.id)})


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
