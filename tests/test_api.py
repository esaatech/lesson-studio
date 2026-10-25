from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_missing_key_returns_a_message(monkeypatch):
    monkeypatch.setenv("ELEVEN_KEY", "")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post(
        "/v1/audio-timings",
        json={"beats": [{"id": "s05-a", "text": "Here is the digit five."}]},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "ELEVEN_KEY is not set"}
    get_settings.cache_clear()


def test_duplicate_beat_ids_are_rejected():
    client = TestClient(app)
    response = client.post(
        "/v1/audio-timings",
        json={
            "beats": [
                {"id": "s05-a", "text": "First line."},
                {"id": "s05-a", "text": "Second line."},
            ]
        },
    )
    assert response.status_code == 422
