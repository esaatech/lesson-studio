import pytest

from app.config import get_settings
from app.runtime_settings import reset_store


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTINGS_FILE", str(tmp_path / "overrides.json"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    get_settings.cache_clear()
    reset_store()
    yield
    get_settings.cache_clear()
    reset_store()
