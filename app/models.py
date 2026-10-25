"""Studio tables. Django does not migrate these."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StudioLesson(Base):
    __tablename__ = "studiolesson"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    beats: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    audio_dir: Mapped[str] = mapped_column(Text, nullable=False, default="")
    html_file: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mp4_file: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        server_default=func.now(),
        onupdate=_now,
    )
