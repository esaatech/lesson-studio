from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.runtime_settings import get_store, reset_store


def test_defaults_match_the_environment(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "AI_GEMINI_MODEL")
    get_settings.cache_clear()
    reset_store()
    settings = get_store().get()

    assert settings.audio.voice_id == "CwhRBWXzGAHq8TQ4Fs17"
    assert settings.audio.padding_seconds == 0.15
    assert settings.script_drafter.provider == "gemini"
    assert settings.visual_generator.model_id == "gemini-2.5-flash"
    assert settings.renderer == "html"
    assert "api_key" not in settings.model_dump()


def test_put_requires_a_token(monkeypatch):
    monkeypatch.setenv("SETTINGS_TOKEN", "")
    get_settings.cache_clear()
    reset_store()
    client = TestClient(app)

    response = client.put("/v1/settings", json={"renderer": "html"})

    assert response.status_code == 403
    assert response.json()["error"] == "SETTINGS_TOKEN is not set"


def test_django_can_replace_a_section_and_audio_uses_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVEN_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "AI_GEMINI_MODEL")
    monkeypatch.setenv("SETTINGS_TOKEN", "django-token")
    get_settings.cache_clear()
    reset_store()
    client = TestClient(app)

    saved = client.put(
        "/v1/settings",
        headers={"X-Settings-Token": "django-token"},
        json={
            "audio": {"voice_id": "voice-from-django", "padding_seconds": 0.4},
            "visual_generator": {
                "provider": "openai",
                "model_id": "gpt-4.1",
                "temperature": 0.1,
                "system_prompt": "Pick a component.",
            },
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["audio"]["voice_id"] == "voice-from-django"
    assert body["audio"]["model_id"] == "eleven_multilingual_v2"
    assert body["audio"]["padding_seconds"] == 0.4
    assert body["visual_generator"]["provider"] == "openai"
    assert body["script_drafter"]["provider"] == "gemini"
    assert body["renderer"] == "html"

    seen: dict[str, object] = {}

    async def fake_synthesize(client, settings, voice_id, model_id, text, beat_id):
        seen["voice_id"] = voice_id
        seen["model_id"] = model_id
        return b"mp3", {
            "characters": ["Hi"],
            "character_start_times_seconds": [0.0],
            "character_end_times_seconds": [1.0],
        }

    monkeypatch.setattr("app.service.synthesize", fake_synthesize)
    result = client.post(
        "/v1/audio-timings",
        json={"beats": [{"id": "s05-a", "text": "Hi"}]},
    )

    assert result.status_code == 200
    assert seen == {"voice_id": "voice-from-django", "model_id": "eleven_multilingual_v2"}
    assert result.json()["beats"][0]["duration"] == 1.4


def test_rejected_token_does_not_change_settings(monkeypatch):
    monkeypatch.setenv("SETTINGS_TOKEN", "django-token")
    get_settings.cache_clear()
    reset_store()
    client = TestClient(app)

    response = client.put(
        "/v1/settings",
        headers={"X-Settings-Token": "wrong"},
        json={"renderer": "manim"},
    )

    assert response.status_code == 403
    assert get_store().get().renderer == "html"


def test_env_chooses_the_provider_and_admin_replaces_it(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "AI_DEEPSEEK_MODEL")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")
    monkeypatch.setenv("SETTINGS_TOKEN", "django-token")
    get_settings.cache_clear()
    reset_store()

    local = get_store().get()
    assert local.script_drafter.provider == "deepseek"
    assert local.script_drafter.model_id == "deepseek-chat"
    assert local.visual_generator.provider == "deepseek"
    visible = local.model_dump_json()
    assert "gemini-secret" not in visible
    assert "deepseek-secret" not in visible
    assert get_settings().ai_api_key("deepseek") == "deepseek-secret"
    assert get_settings().ai_api_key("gemini") == "gemini-secret"

    client = TestClient(app)
    saved = client.put(
        "/v1/settings",
        headers={"X-Settings-Token": "django-token"},
        json={
            "script_drafter": {
                "provider": "gemini",
                "model_id": "gemini-2.5-flash",
                "temperature": 0.4,
                "system_prompt": "Draft the beats.",
            }
        },
    )

    assert saved.status_code == 200
    body = saved.json()
    assert body["script_drafter"]["provider"] == "gemini"
    assert body["visual_generator"]["provider"] == "deepseek"
    assert "gemini-secret" not in saved.text


def test_unknown_provider_names_the_model_lines(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.setenv("AI_PROVIDER", "claude")
    get_settings.cache_clear()

    try:
        get_settings()
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected AI_PROVIDER to be rejected")

    assert "AI_GEMINI_MODEL" in message
    assert "AI_DEEPSEEK_MODEL" in message
    assert "AI_OPENAI_MODEL" in message


def test_settings_command_prints_the_active_voice(capsys):
    from app.cli import main

    assert main(["settings"]) == 0
    assert "CwhRBWXzGAHq8TQ4Fs17" in capsys.readouterr().out
