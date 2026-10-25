"""Write beats onto a lesson, either in this request or from the Cloud Tasks worker."""

import uuid

from app.ai_client import AIError
from app.lesson_store import LessonRecord, LessonStore
from app.script_draft import draft_beats
from app.script_queue import enqueue_script, is_last_attempt, uses_queue


class ScriptFailed(Exception):
    def __init__(self, message: str, lesson_id: uuid.UUID) -> None:
        self.message = message
        self.lesson_id = lesson_id
        super().__init__(message)


async def write_script(store: LessonStore, lesson: LessonRecord) -> LessonRecord:
    if uses_queue():
        enqueue_script(lesson.id)
        return lesson
    try:
        beats = await draft_beats(lesson.topic)
    except AIError as exc:
        store.mark_status(lesson.id, "draft_failed")
        raise ScriptFailed(exc.message, lesson.id) from exc
    saved = store.save_script(lesson.id, beats)
    if saved is None:
        raise ScriptFailed("Lesson not found", lesson.id)
    return saved


async def run_queued_script(store: LessonStore, lesson_id: uuid.UUID, retry_count: int) -> tuple[int, dict]:
    lesson = store.get(lesson_id)
    if lesson is None or lesson.status != "drafting":
        status = "missing" if lesson is None else lesson.status
        return 200, {"status": status}
    try:
        beats = await draft_beats(lesson.topic)
    except AIError as exc:
        if is_last_attempt(retry_count):
            store.mark_status(lesson_id, "draft_failed")
            return 200, {"status": "draft_failed", "error": exc.message}
        return 500, {"error": exc.message}
    saved = store.save_script(lesson_id, beats)
    if saved is None:
        return 200, {"status": "missing"}
    return 200, {"status": saved.status, "id": str(saved.id)}
