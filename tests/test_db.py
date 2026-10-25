from app.config import get_settings
from app.db import sqlalchemy_url


def test_cloud_sql_socket_skips_the_port(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_HOST", "/cloudsql/esaasolution:us-central1:sbtacedemy")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "stbacedemy-backened")
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_SSLMODE", "disable")
    get_settings.cache_clear()

    url = sqlalchemy_url()

    assert url.startswith("postgresql+psycopg://postgres:secret@/stbacedemy-backened?host=")
    assert "cloudsql" in url
    assert ":5432" not in url
    get_settings.cache_clear()
