"""The job of a spoken line: intro, wording, or concept."""

from typing import Literal

BeatKind = Literal["intro", "wording", "concept"]
BEAT_KINDS = ("intro", "wording", "concept")
_ALIASES = {"template": "concept"}


def parse_kind(value: object, default: str | None = None) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        cleaned = _ALIASES.get(cleaned, cleaned)
        if cleaned in BEAT_KINDS:
            return cleaned
    return default
