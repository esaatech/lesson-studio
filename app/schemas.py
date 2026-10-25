from pydantic import BaseModel, Field, field_validator, model_validator


class BeatIn(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    text: str = Field(min_length=1, max_length=2000)
    checkpoint: bool = False

    @field_validator("text")
    @classmethod
    def text_must_contain_words(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class LessonAudioRequest(BaseModel):
    voice_id: str | None = None
    model_id: str | None = None
    beats: list[BeatIn] = Field(min_length=1, max_length=50)

    @field_validator("voice_id", "model_id")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def beat_ids_must_be_unique(self) -> "LessonAudioRequest":
        ids = [beat.id for beat in self.beats]
        if len(ids) != len(set(ids)):
            raise ValueError("beat ids must be unique")
        return self


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class BeatOut(BaseModel):
    id: str
    audio_file: str
    start: float
    duration: float
    end: float
    words: list[WordTiming]
    pause_after: float | None = None


class LessonAudioResponse(BaseModel):
    request_id: str
    output_dir: str
    beats: list[BeatOut]
    total_duration: float
