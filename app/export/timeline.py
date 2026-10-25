"""Frame times and the audio mix for one lesson recording."""

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioGraph:
    inputs: list[Path]
    filter: str
    delays_ms: list[int]


def frame_times(total_seconds: float, fps: int) -> list[float]:
    count = math.ceil(total_seconds * fps - 1e-9)
    return [index / fps for index in range(count)]


def audio_graph(beats: list[dict], pad_seconds: float, directory: Path) -> AudioGraph:
    inputs: list[Path] = []
    delays_ms: list[int] = []
    chains: list[str] = []
    for beat in beats:
        name = beat.get("audio_file")
        if not name:
            continue
        path = Path(name)
        if not path.is_absolute():
            path = directory / path
        slot = round(float(beat["end"]) - float(beat["start"]), 3)
        delay = int(round(float(beat["start"]) * 1000))
        label = f"a{len(inputs)}"
        chains.append(
            f"[{len(inputs)}:a]atrim=start=0:end={slot},asetpts=PTS-STARTPTS,"
            f"adelay={delay}:all=1,apad=whole_dur={pad_seconds:.3f}[{label}]"
        )
        inputs.append(path)
        delays_ms.append(delay)
    if not inputs:
        raise ValueError("Lesson has no audio files.")
    mix = "".join(f"[a{index}]" for index in range(len(inputs)))
    chains.append(
        f"{mix}amix=inputs={len(inputs)}:duration=longest:dropout_transition=0:normalize=0,"
        f"atrim=0:{pad_seconds:.3f},asetpts=N/SR/TB[a]"
    )
    return AudioGraph(inputs=inputs, filter=";".join(chains), delays_ms=delays_ms)
