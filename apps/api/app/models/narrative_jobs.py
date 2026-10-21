"""Durable per-generation narrative extraction intent, recorded with parse publication."""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from app.models.generations import SourceGeneration  # noqa: F401  (registers the referenced table)
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class NarrativeJob(Base):
    __tablename__ = "narrative_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_generations.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # Last stage reached: queued, entities, events, facts, narrative_ready or failed.
    stage: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
