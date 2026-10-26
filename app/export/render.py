"""Step the lesson page one frame at a time and join those frames with the audio."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.export.timeline import audio_graph, frame_times
from app.lesson.page import load_lesson_record, write_lesson_page


class ExportError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


async def export_lesson(directory: Path, fps: int = 30) -> dict:
    directory = directory.expanduser().resolve()
    if fps < 1:
        raise ExportError("fps must be at least 1.")
    if shutil.which("ffmpeg") is None:
        raise ExportError("ffmpeg is not installed.")
    if not (directory / "index.html").is_file() and not (directory / "lesson.json").is_file():
        raise ExportError(f"Lesson folder has no index.html: {directory}")

    record = load_lesson_record(directory)
    page = write_lesson_page(record["id"], record["beats"], record["total_duration"], directory)
    times = frame_times(float(record["total_duration"]), fps)
    pad = len(times) / fps
    graph = audio_graph(record["beats"], pad, directory)
    missing = [path for path in graph.inputs if not path.is_file()]
    if missing:
        names = ", ".join(path.name for path in missing)
        raise ExportError(f"Audio file not found: {names}")

    mp4 = directory / f"{record['id']}.mp4"
    with tempfile.TemporaryDirectory(prefix="lesson-export-") as temporary:
        folder = Path(temporary)
        wav = folder / "lesson.wav"
        _run_ffmpeg(_audio_command(graph, wav), "Could not mix the lesson audio.")
        await _capture_frames(page, times, folder)
        _run_ffmpeg(_video_command(folder, wav, mp4, fps), "Could not write the MP4.")

    return {
        "id": record["id"],
        "mp4_file": str(mp4),
        "total_duration": record["total_duration"],
        "video_duration": round(pad, 3),
        "frames": len(times),
        "fps": fps,
    }


def _audio_command(graph, wav: Path) -> list[str]:
    command = ["ffmpeg", "-y"]
    for path in graph.inputs:
        command.extend(["-i", str(path)])
    command.extend(["-filter_complex", graph.filter, "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "44100", str(wav)])
    return command


def _video_command(frames: Path, wav: Path, mp4: Path, fps: int) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        "0",
        "-i",
        str(frames / "frame_%04d.png"),
        "-i",
        str(wav),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(mp4),
    ]


def _run_ffmpeg(command: list[str], failure: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return
    tail = "\n".join(result.stderr.splitlines()[-20:])
    raise ExportError(f"{failure}\n{tail}")


async def _capture_frames(page_path: Path, times: list[float], folder: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ExportError("Playwright is not installed. Run: poetry run playwright install chromium") from exc

    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright)
        page = await browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        await page.goto(f"{page_path.as_uri()}?capture=1")
        await page.wait_for_function("() => typeof window.renderLessonFrame === 'function'")
        total = len(times)
        for index, time in enumerate(times):
            await page.evaluate("(t) => window.renderLessonFrame(t)", time)
            await page.locator("#stage").screenshot(path=str(folder / f"frame_{index:04d}.png"))
            if index % 30 == 0 or index == total - 1:
                print(f"frame {index + 1}/{total}", file=sys.stderr)
        await browser.close()


async def _launch_browser(playwright):
    errors: list[str] = []
    for options in ({}, {"channel": "chrome"}):
        try:
            return await playwright.chromium.launch(**options)
        except Exception as exc:
            errors.append(str(exc).splitlines()[0])
    detail = errors[-1] if errors else "no browser"
    raise ExportError(f"Could not open a browser ({detail}). Run: poetry run playwright install chromium")
