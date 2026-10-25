"""Build a Pydantic AI model from the active provider. Keys stay in the environment."""

from app.config import get_settings
from app.runtime_settings import AITaskSettings


class AIError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def build_model(task: AITaskSettings):
    key = get_settings().ai_api_key(task.provider)
    if not key:
        env_name = {
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(task.provider, "API key")
        raise AIError(f"{env_name} is not set")

    if task.provider == "gemini":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(task.model_id, provider=GoogleProvider(api_key=key))

    if task.provider == "deepseek":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.deepseek import DeepSeekProvider

        return OpenAIChatModel(task.model_id, provider=DeepSeekProvider(api_key=key))

    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIChatModel(task.model_id, provider=OpenAIProvider(api_key=key))
