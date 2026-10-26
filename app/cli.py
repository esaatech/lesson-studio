"""Local commands. FastAPI has no Django-style command registry."""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError

from app.ai_client import AIError
from app.elevenlabs import ElevenLabsError
from app.runtime_settings import get_store
from app.schemas import LessonAudioRequest
from app.service import render_lesson_audio
from app.db import DatabaseError, create_tables
from app.export.render import ExportError, export_lesson
from app.export_service import run_saved_export
from app.lesson.build import build_lesson
from app.visuals.generate import generate_visual, preview_visual
from app.visuals.schema import VisualBeat

DEFAULT_REQUEST = "examples/slide5-request.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manage.py")
    subcommands = parser.add_subparsers(dest="command")

    audio = subcommands.add_parser("audio", help="Generate one mp3 per beat and print timings")
    audio.add_argument(
        "request",
        nargs="?",
        default=DEFAULT_REQUEST,
        help=f"Beat JSON file (default: {DEFAULT_REQUEST})",
    )
    subcommands.add_parser("settings", help="Print the settings the service is using")
    visual = subcommands.add_parser("visual", help="Choose a component for a beat and write its page")
    visual.add_argument("request", help="JSON file for one beat, or an object with a beats list")
    lesson = subcommands.add_parser("lesson", help="Play the beats in order on one lesson page")
    lesson.add_argument("request", help="Lesson JSON file")
    export = subcommands.add_parser("export", help="Record the lesson page to an MP4")
    export.add_argument("lesson", help="Lesson folder that contains index.html")
    export.add_argument("--fps", type=int, default=30)
    job = subcommands.add_parser("export-job", help="Record one saved lesson. The Cloud Run Job runs this.")
    job.add_argument("lesson_id", help="Lesson id that is already marked exporting")
    subcommands.add_parser("migrate", help="Create the studiolesson table")

    args = parser.parse_args(argv)
    if args.command == "audio":
        return asyncio.run(render_request(Path(args.request)))
    if args.command == "settings":
        print(get_store().get().model_dump_json(indent=2))
        return 0
    if args.command == "visual":
        return asyncio.run(render_visuals(Path(args.request)))
    if args.command == "lesson":
        return asyncio.run(render_lesson(Path(args.request)))
    if args.command == "export":
        return asyncio.run(render_export(Path(args.lesson), args.fps))
    if args.command == "export-job":
        _configure_logging()
        try:
            lesson_id = uuid.UUID(args.lesson_id)
        except ValueError:
            print("Lesson id is not valid.", file=sys.stderr)
            return 1
        return run_saved_export(lesson_id)
    if args.command == "migrate":
        return migrate_database()

    parser.print_help()
    return 1


async def render_request(path: Path) -> int:
    _configure_logging()
    if not path.is_file():
        print(f"Request file not found: {path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(path.read_text())
        request = LessonAudioRequest.model_validate(payload)
    except json.JSONDecodeError as exc:
        print(f"Request file is not valid JSON: {exc.msg}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print("Request JSON is not a valid beat list.", file=sys.stderr)
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            print(f"{location}: {error['msg']}", file=sys.stderr)
        return 1

    try:
        result = await render_lesson_audio(request)
    except ElevenLabsError as exc:
        print(exc.message, file=sys.stderr)
        if exc.beat_id:
            print(f"beat: {exc.beat_id}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2, exclude_none=True))
    return 0


async def render_visuals(path: Path) -> int:
    _configure_logging()
    if not path.is_file():
        print(f"Request file not found: {path}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"Request file is not valid JSON: {exc.msg}", file=sys.stderr)
        return 1

    for item in _visual_items(payload):
        try:
            if "component" in item and "settings" in item:
                result = preview_visual(item)
            else:
                result = await generate_visual(VisualBeat.model_validate(item))
        except ValidationError as exc:
            print("Request JSON is not a valid visual beat.", file=sys.stderr)
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"])
                print(f"{location}: {error['msg']}", file=sys.stderr)
            return 1
        except AIError as exc:
            print(exc.message, file=sys.stderr)
            beat_id = item.get("id", "")
            if beat_id:
                print(f"beat: {beat_id}", file=sys.stderr)
            return 1
        print(result.model_dump_json(indent=2))
    return 0


async def render_lesson(path: Path) -> int:
    _configure_logging()
    if not path.is_file():
        print(f"Request file not found: {path}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(path.read_text())
        result = await build_lesson(payload)
    except json.JSONDecodeError as exc:
        print(f"Request file is not valid JSON: {exc.msg}", file=sys.stderr)
        return 1
    except (ValidationError, AIError) as exc:
        message = exc.message if isinstance(exc, AIError) else "Lesson JSON is not valid."
        print(message, file=sys.stderr)
        if isinstance(exc, ValidationError):
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"])
                print(f"{location}: {error['msg']}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


async def render_export(directory: Path, fps: int) -> int:
    try:
        result = await export_lesson(directory, fps)
    except ExportError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def migrate_database() -> int:
    try:
        create_tables()
    except DatabaseError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print("studiolesson")
    return 0


def _visual_items(payload: dict) -> list[dict]:
    if isinstance(payload, dict) and "beats" in payload and "component" not in payload:
        return list(payload["beats"])
    return [payload]


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
