"""Connection to the academy PostgreSQL database. The studio owns studiolesson."""

from collections.abc import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


class DatabaseError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


_engine: Engine | None = None


def database_configured(settings: Settings | None = None) -> bool:
    current = settings or get_settings()
    if current.database_url.strip():
        return True
    return bool(current.db_host.strip() and current.db_name.strip() and current.db_user.strip())


def sqlalchemy_url(settings: Settings | None = None) -> str:
    current = settings or get_settings()
    explicit = current.database_url.strip()
    if explicit:
        if explicit.startswith("postgres://"):
            return "postgresql+psycopg://" + explicit[len("postgres://") :]
        if explicit.startswith("postgresql://"):
            return "postgresql+psycopg://" + explicit[len("postgresql://") :]
        return explicit
    if not database_configured(current):
        return ""
    user = quote_plus(current.db_user)
    password = quote_plus(current.db_password.get_secret_value())
    url = f"postgresql+psycopg://{user}:{password}@{current.db_host}:{current.db_port}/{current.db_name}"
    if current.db_sslmode.strip():
        url += f"?sslmode={quote_plus(current.db_sslmode.strip())}"
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    url = sqlalchemy_url()
    if not url:
        raise DatabaseError("Database is not configured")
    _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def create_tables() -> None:
    from app.models import StudioLesson  # noqa: F401

    try:
        Base.metadata.create_all(get_engine())
    except Exception as exc:
        raise DatabaseError(_public_database_message(exc)) from exc


def get_session() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _public_database_message(exc: Exception) -> str:
    text = str(exc)
    password = get_settings().db_password.get_secret_value()
    if password:
        text = text.replace(password, "***")
        text = text.replace(quote_plus(password), "***")
    return text
