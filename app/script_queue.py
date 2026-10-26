"""Enqueue script generation. With no queue configured, the request writes the beats itself."""

import base64
import json
import logging
import uuid

from app.config import get_settings

logger = logging.getLogger(__name__)


class CloudTaskError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def uses_queue() -> bool:
    settings = get_settings()
    if not settings.cloud_tasks_queue.strip():
        return False
    missing = []
    if not settings.cloud_tasks_project.strip():
        missing.append("CLOUD_TASKS_PROJECT")
    if not settings.cloud_tasks_target_url.strip():
        missing.append("CLOUD_TASKS_TARGET_URL")
    if not settings.cloud_tasks_service_account.strip():
        missing.append("CLOUD_TASKS_SERVICE_ACCOUNT")
    if missing:
        raise CloudTaskError("Script queue is incomplete. Set " + ", ".join(missing) + ".")
    return True


def enqueue_script(lesson_id: uuid.UUID) -> str:
    if not uses_queue():
        raise CloudTaskError("Cloud Tasks queue is not configured.")
    settings = get_settings()
    return _enqueue(
        lesson_id,
        queue=settings.cloud_tasks_queue.strip(),
        target=settings.cloud_tasks_target_url.strip(),
        task_id=f"studio-script-{lesson_id}",
        failure="Failed to enqueue the script",
    )


def uses_render_queue() -> bool:
    settings = get_settings()
    if not settings.cloud_tasks_render_queue.strip():
        return False
    missing = []
    if not settings.cloud_tasks_project.strip():
        missing.append("CLOUD_TASKS_PROJECT")
    if not settings.cloud_tasks_render_target_url.strip():
        missing.append("CLOUD_TASKS_RENDER_TARGET_URL")
    if not settings.cloud_tasks_service_account.strip():
        missing.append("CLOUD_TASKS_SERVICE_ACCOUNT")
    if missing:
        raise CloudTaskError("Render queue is incomplete. Set " + ", ".join(missing) + ".")
    return True


def enqueue_render(lesson_id: uuid.UUID) -> str:
    if not uses_render_queue():
        raise CloudTaskError("Render queue is not configured.")
    settings = get_settings()
    return _enqueue(
        lesson_id,
        queue=settings.cloud_tasks_render_queue.strip(),
        target=settings.cloud_tasks_render_target_url.strip(),
        task_id=f"studio-render-{lesson_id}-{uuid.uuid4().hex[:8]}",
        failure="Failed to enqueue the lesson",
    )


def _enqueue(lesson_id: uuid.UUID, *, queue: str, target: str, task_id: str, failure: str) -> str:
    settings = get_settings()
    project = settings.cloud_tasks_project.strip()
    location = settings.cloud_tasks_location.strip() or "us-central1"
    service_account = settings.cloud_tasks_service_account.strip()
    audience = target
    if queue == settings.cloud_tasks_queue.strip() and settings.cloud_tasks_oidc_audience.strip():
        audience = settings.cloud_tasks_oidc_audience.strip()
    parent = f"projects/{project}/locations/{location}/queues/{queue}"
    task_name = f"{parent}/tasks/{task_id}"
    deadline = settings.cloud_tasks_dispatch_deadline_seconds
    body = {
        "task": {
            "name": task_name,
            "dispatchDeadline": f"{deadline}s",
            "httpRequest": {
                "httpMethod": "POST",
                "url": target,
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(json.dumps({"lesson_id": str(lesson_id)}).encode()).decode("ascii"),
                "oidcToken": {"serviceAccountEmail": service_account, "audience": audience},
            },
        }
    }
    access_token = _access_token()
    import httpx

    try:
        response = httpx.post(
            f"https://cloudtasks.googleapis.com/v2/{parent}/tasks",
            json=body,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=30.0,
        )
    except Exception as exc:
        logger.warning("Cloud Tasks create failed for %s: %s", lesson_id, exc.__class__.__name__)
        raise CloudTaskError("Failed to contact Cloud Tasks.") from exc
    if response.status_code == 409:
        return task_id
    if response.status_code >= 400:
        raise CloudTaskError(f"{failure} ({response.status_code}).")
    return task_id


def verify_worker(authorization: str, retry_header: str, audience: str | None = None) -> int:
    settings = get_settings()
    service_account = settings.cloud_tasks_service_account.strip()
    if audience is None:
        audience = settings.cloud_tasks_oidc_audience.strip() or settings.cloud_tasks_target_url.strip()
    else:
        audience = audience.strip()
    if not service_account or not audience:
        raise CloudTaskError("Cloud Tasks worker auth is not configured.", 403)
    if not authorization.startswith("Bearer "):
        raise CloudTaskError("Missing Cloud Tasks OIDC token.", 403)
    token = authorization[7:].strip()
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(token, google.auth.transport.requests.Request(), audience=audience)
    except Exception as exc:
        raise CloudTaskError("Invalid Cloud Tasks OIDC token.", 403) from exc
    if info.get("email") != service_account or not info.get("email_verified", False):
        raise CloudTaskError("Unexpected Cloud Tasks identity.", 403)
    try:
        return max(int(retry_header), 0)
    except (TypeError, ValueError):
        return 0


def is_last_attempt(retry_count: int) -> bool:
    return retry_count + 1 >= get_settings().cloud_tasks_max_attempts


def _access_token() -> str:
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(google.auth.transport.requests.Request())
    except Exception as exc:
        raise CloudTaskError("Could not authenticate to Cloud Tasks.") from exc
    if not credentials.token:
        raise CloudTaskError("Could not authenticate to Cloud Tasks.")
    return credentials.token
