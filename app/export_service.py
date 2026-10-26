"""Record a finished lesson page to an MP4 on this machine."""

import logging
import uuid
from pathlib import Path

from app.export.render import ExportError, export_lesson
from app.lesson_store import LessonRecord, LessonStore

logger = logging.getLogger(__name__)


class ExportFailed(Exception):
    def __init__(self, message: str, lesson_id: uuid.UUID) -> None:
        self.message = message
        self.lesson_id = lesson_id
        super().__init__(message)


async def write_export(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
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
