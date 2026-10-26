"""Record a finished lesson page to an MP4. Cloud Run starts a job; this machine records it here."""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import DatabaseError, get_engine
from app.export.render import ExportError, export_lesson
from app.export_job import ExportJobError, start_export_job, uses_export_job
from app.lesson_store import LessonRecord, LessonStore, SqlLessonStore

logger = logging.getLogger(__name__)


class ExportFailed(Exception):
    def __init__(self, message: str, lesson_id: uuid.UUID) -> None:
        self.message = message
        self.lesson_id = lesson_id
        super().__init__(message)


async def write_export(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
    if uses_export_job():
        try:
            start_export_job(lesson.id)
        except ExportJobError as exc:
            store.mark_status(lesson.id, "export_failed")
            raise ExportFailed(exc.message, lesson.id) from exc
        return lesson
    return await _record_export(store, lesson)


def run_saved_export(lesson_id: uuid.UUID) -> int:
    """Record one lesson that is already marked exporting. The Cloud Run Job runs this."""
    try:
        session = Session(get_engine())
    except DatabaseError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    store = SqlLessonStore(session)
    try:
        lesson = store.get(lesson_id)
        if lesson is None:
            print("Lesson not found", file=sys.stderr)
            return 1
        if lesson.status != "exporting":
            return 0
        try:
            saved = asyncio.run(_record_export(store, lesson))
        except ExportFailed as exc:
            session.commit()
            print(exc.message, file=sys.stderr)
            return 1
        session.commit()
        return 0 if saved.status == "exported" else 1
    finally:
        session.close()


async def _record_export(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
    directory = Path(lesson.html_file).parent
    try:
        result = await export_lesson(directory)
    except ExportError as exc:
        logger.warning("lesson export failed for %s: %s", lesson.id, exc.message.splitlines()[0])
        store.mark_status(lesson.id, "export_failed")
        raise ExportFailed(_teacher_message(exc.message), lesson.id) from exc
    saved = store.save_export(lesson.id, result["mp4_file"])
    if saved is None:
        raise ExportFailed("Lesson not found", lesson.id)
    return saved


def _teacher_message(detail: str) -> str:
    first = detail.splitlines()[0].strip()
    if not first or len(first) > 160:
        return "The video could not be made."
    return first
