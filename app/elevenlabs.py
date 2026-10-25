"""ElevenLabs text-to-speech with character timestamps."""

import base64
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


class ElevenLabsError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        beat_id: str | None = None,
        upstream: bool = True,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.beat_id = beat_id
        self.upstream = upstream


_PAID_PLAN_MARKERS = (
    "paid",
    "subscription",
    "upgrade",
    "library voice",
    "payment_required",
    "free users",
    "not available",
)


def extract_error_message(status_code: int, payload: Any) -> str:
    """Turn an ElevenLabs error body into a message safe to return to the caller."""
    message, status_name = _read_detail(payload)
    haystack = f"{message} {status_name}".lower()

    if status_code == 401 or status_name in {"invalid_api_key", "unauthorized"}:
        return f"Invalid ElevenLabs API key: {message}"
    if status_code == 429:
        return f"ElevenLabs rate limit: {message}"
    if any(marker in haystack for marker in _PAID_PLAN_MARKERS):
        return f"ElevenLabs voice is not available on this plan: {message}"
    return f"ElevenLabs request failed: {message}"


def _read_detail(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        text = str(payload).strip() or "empty error response"
        return text, ""

    detail = payload.get("detail", payload)
    if isinstance(detail, str):
        return detail, ""
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts) or "request rejected", ""
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("status") or detail.get("code") or "request rejected"
        status_name = str(detail.get("status") or detail.get("code") or "")
        return str(message), status_name
    return "request rejected", ""


def public_error_status(status_code: int) -> int:
    if status_code in {400, 401, 402, 403, 422, 429}:
        return status_code
    if status_code == 500:
        return 500
    return 502


async def synthesize(
    client: httpx.AsyncClient,
    settings: Settings,
    voice_id: str,
    model_id: str,
    text: str,
    beat_id: str,
) -> tuple[bytes, dict]:
    url = (
        f"{settings.eleven_base_url.rstrip('/')}"
        f"/v1/text-to-speech/{quote(voice_id, safe='')}/with-timestamps"
    )
    try:
        response = await client.post(
            url,
            headers={
                "xi-api-key": settings.api_key(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"text": text, "model_id": model_id},
        )
    except httpx.RequestError as exc:
        raise ElevenLabsError(
            502,
            f"Could not reach ElevenLabs: {exc.__class__.__name__}",
            beat_id,
        ) from exc

    if response.status_code >= 400:
        message = extract_error_message(response.status_code, _json_or_text(response))
        raise ElevenLabsError(response.status_code, message, beat_id)

    try:
        data = response.json()
    except ValueError as exc:
        raise ElevenLabsError(502, "ElevenLabs returned a response that was not JSON", beat_id) from exc

    audio_base64 = data.get("audio_base64")
    if not isinstance(audio_base64, str) or not audio_base64:
        raise ElevenLabsError(502, "ElevenLabs response did not include audio", beat_id)

    try:
        audio = base64.b64decode(audio_base64, validate=False)
    except (ValueError, TypeError) as exc:
        raise ElevenLabsError(502, "ElevenLabs audio could not be decoded", beat_id) from exc
    if not audio:
        raise ElevenLabsError(502, "ElevenLabs audio was empty", beat_id)

    alignment = data.get("alignment") or data.get("normalized_alignment")
    if not isinstance(alignment, dict):
        raise ElevenLabsError(502, "ElevenLabs response did not include alignment", beat_id)
    return audio, alignment


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]
