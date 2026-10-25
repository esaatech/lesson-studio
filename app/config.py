from functools import lru_cache
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value written in AI_PROVIDER. Each name is the model line already in .env.
AI_PROVIDER_KEYS = {
    "AI_GEMINI_MODEL": "gemini",
    "AI_DEEPSEEK_MODEL": "deepseek",
    "AI_OPENAI_MODEL": "openai",
    "gemini": "gemini",
    "deepseek": "deepseek",
    "openai": "openai",
}


class Settings(BaseSettings):
    """Service settings. The API key is read from ELEVEN_KEY and kept as a secret."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    eleven_key: SecretStr = SecretStr("")
    eleven_voice_id: str = "CwhRBWXzGAHq8TQ4Fs17"
    eleven_model_id: str = "eleven_multilingual_v2"
    beat_padding_seconds: float = Field(default=0.15, ge=0)
    checkpoint_pause_seconds: float = Field(default=2.0, ge=0)
    eleven_concurrency: int = Field(default=1, ge=1, le=4)
    output_dir: str = "output"
    eleven_base_url: str = "https://api.elevenlabs.io"
    request_timeout_seconds: float = Field(default=120, gt=0)
    settings_file: str = "config/overrides.json"
    settings_token: SecretStr = SecretStr("")
    ai_provider: str = "AI_GEMINI_MODEL"
    ai_gemini_model: str = "gemini-2.5-flash"
    ai_deepseek_model: str = "deepseek-chat"
    ai_openai_model: str = "gpt-4o-mini"
    gemini_api_key: SecretStr = SecretStr("")
    deepseek_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")

    @field_validator("ai_provider")
    @classmethod
    def provider_must_name_a_model_line(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in AI_PROVIDER_KEYS:
            names = "AI_GEMINI_MODEL, AI_DEEPSEEK_MODEL, AI_OPENAI_MODEL"
            raise ValueError(f"AI_PROVIDER must be one of: {names}")
        return cleaned

    def resolved_ai_provider(self) -> str:
        return AI_PROVIDER_KEYS[self.ai_provider]

    def api_key(self) -> str:
        return self.eleven_key.get_secret_value().strip()

    def ai_api_key(self, provider: str) -> str:
        keys = {
            "gemini": self.gemini_api_key,
            "deepseek": self.deepseek_api_key,
            "openai": self.openai_api_key,
        }
        secret = keys.get(provider)
        if secret is None:
            return ""
        return secret.get_secret_value().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
