from pathlib import Path

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from app.ai_client import AIError
from app.config import get_settings
from app.elevenlabs import ElevenLabsError, public_error_status
from app.runtime_settings import RuntimeSettings, SettingsPatch, get_store, token_matches
from app.schemas import LessonAudioRequest, LessonAudioResponse
from app.service import render_lesson_audio
from app.visuals.generate import generate_visual
from app.visuals.render_html import html_with_inline_audio
from app.visuals.schema import VisualBeat, VisualRunRequest, VisualRunResponse, WordTime

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/v1/audio-timings",
    response_model=LessonAudioResponse,
    response_model_exclude_none=True,
)
async def create_audio_timings(body: LessonAudioRequest) -> LessonAudioResponse:
    try:
        return await render_lesson_audio(body)
    except ElevenLabsError as exc:
        content: dict[str, str | int] = {"error": exc.message}
        if exc.beat_id:
            content["beat_id"] = exc.beat_id
        if exc.upstream:
            content["upstream_status"] = exc.status_code
        return JSONResponse(status_code=public_error_status(exc.status_code), content=content)


@router.post("/v1/visuals", response_model=VisualRunResponse)
async def create_visual(body: VisualRunRequest) -> VisualRunResponse | JSONResponse:
    try:
        beat = VisualBeat.model_validate(body.model_dump(exclude={"generate_audio", "visual_generator"}))
        if body.generate_audio:
            audio = await render_lesson_audio(LessonAudioRequest(beats=[{"id": beat.id, "text": beat.text}]))
            item = audio.beats[0]
            beat.duration = item.duration
            beat.words = [WordTime.model_validate(word.model_dump()) for word in item.words]
            beat.audio_file = str(Path(audio.output_dir) / item.audio_file)
        visual = await generate_visual(beat, task=body.visual_generator)
        page = Path(visual.html_file)
        return VisualRunResponse(
            **visual.model_dump(),
            html=html_with_inline_audio(page, visual) if page.is_file() else "",
        )
    except ElevenLabsError as exc:
        content: dict[str, str | int] = {"error": exc.message}
        if exc.beat_id:
            content["beat_id"] = exc.beat_id
        if exc.upstream:
            content["upstream_status"] = exc.status_code
        return JSONResponse(status_code=public_error_status(exc.status_code), content=content)
    except AIError as exc:
        status_code = 400 if exc.message.endswith("is not set") else 502
        return JSONResponse(status_code=status_code, content={"error": exc.message})


@router.get("/v1/settings", response_model=RuntimeSettings)
async def read_settings() -> RuntimeSettings:
    return get_store().get()


@router.put("/v1/settings", response_model=RuntimeSettings)
async def update_settings(
    body: SettingsPatch,
    x_settings_token: str = Header(default=""),
) -> RuntimeSettings | JSONResponse:
    expected = get_settings().settings_token.get_secret_value().strip()
    if not expected:
        return JSONResponse(status_code=403, content={"error": "SETTINGS_TOKEN is not set"})
    if not token_matches(x_settings_token, expected):
        return JSONResponse(status_code=403, content={"error": "Settings token was rejected"})
    return get_store().update(body)
