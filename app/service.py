"""Generate one clip per beat and place the beats on a lesson clock.

This function is the piece later studio steps can call. The HTTP route is a
thin wrapper, so authentication can be added in front of the route later.
"""

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.config import Settings, get_settings
from app.elevenlabs import ElevenLabsError, synthesize
from app.runtime_settings import get_store
from app.schemas import LessonAudioRequest, LessonAudioResponse
from app.timing import build_timeline, group_characters_into_words

logger = logging.getLogger(__name__)


async def render_lesson_audio(
    request: LessonAudioRequest,
    settings: Settings | None = None,
) -> LessonAudioResponse:
    settings = settings or get_settings()
    if not settings.api_key():
        raise ElevenLabsError(500, "ELEVEN_KEY is not set", upstream=False)

    runtime = get_store().get()
    voice_id = request.voice_id or runtime.audio.voice_id
    model_id = request.model_id or runtime.audio.model_id
    request_id = uuid.uuid4().hex
    folder = Path(settings.output_dir) / request_id
    folder.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(runtime.audio.concurrency)
    timeout = httpx.Timeout(settings.request_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:

        async def render_beat(index: int, beat):
            async with semaphore:
                audio, alignment = await synthesize(
                    client,
                    settings,
                    voice_id,
                    model_id,
                    beat.text,
                    beat.id,
                )
            audio_file = f"{beat.id}.mp3"
            try:
                (folder / audio_file).write_bytes(audio)
                words = group_characters_into_words(alignment)
            except ValueError as exc:
                raise ElevenLabsError(502, str(exc), beat.id) from exc
            except OSError as exc:
                raise ElevenLabsError(500, "Could not save the audio file", beat.id, upstream=False) from exc
            logger.info("rendered beat %s", beat.id)
            return index, (beat.id, audio_file, words, beat.checkpoint)

        tasks = [
            asyncio.create_task(render_beat(index, beat))
            for index, beat in enumerate(request.beats)
        ]
        try:
            rendered_by_index = await asyncio.gather(*tasks)
        except ElevenLabsError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    rendered = [item for _, item in sorted(rendered_by_index, key=lambda pair: pair[0])]
    beats, total_duration = build_timeline(
        rendered,
        runtime.audio.padding_seconds,
        runtime.audio.checkpoint_pause_seconds,
    )
    return LessonAudioResponse(
        request_id=request_id,
        output_dir=str(folder),
        beats=beats,
        total_duration=total_duration,
    )
