"""Safe provider-call lineage: references, digests, versions and usage, never source text."""

import uuid
from datetime import datetime

from app.models.access import Base
from app.models.generations import SourceGeneration  # noqa: F401  (registers the referenced table)
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_generations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    purpose: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSONB)
    input_refs: Mapped[list[str]] = mapped_column(JSONB)
    input_sha256: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int]
