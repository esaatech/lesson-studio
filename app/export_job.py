"""Start the Cloud Run Job that records a lesson. Local export leaves this unset."""

import logging
import uuid

import httpx

from app.config import get_settings
from app.script_queue import _access_token

logger = logging.getLogger(__name__)


class ExportJobError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def uses_export_job() -> bool:
    return bool(get_settings().export_job.strip())


def start_export_job(lesson_id: uuid.UUID) -> str:
    settings = get_settings()
    job = settings.export_job.strip()
    project = settings.export_job_project.strip() or settings.cloud_tasks_project.strip()
    location = settings.export_job_location.strip() or settings.cloud_tasks_location.strip() or "us-central1"
    if not project:
        raise ExportJobError("EXPORT_JOB_PROJECT is not set.")
    name = f"projects/{project}/locations/{location}/jobs/{job}"
    body = {"overrides": {"containerOverrides": [{"args": [str(lesson_id)]}]}}
    try:
        response = httpx.post(
            f"https://run.googleapis.com/v2/{name}:run",
            json=body,
            headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"},
            timeout=30.0,
        )
    except Exception as exc:
        logger.warning("export job start failed for %s: %s", lesson_id, exc.__class__.__name__)
        raise ExportJobError("The video could not be started.") from exc
    if response.status_code >= 400:
        logger.warning("export job start rejected for %s: %s", lesson_id, response.status_code)
        raise ExportJobError("The video could not be started.")
    return name
