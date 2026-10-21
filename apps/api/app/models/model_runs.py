"""Derivation and provider-call lineage: references, digests, versions and usage, never source text."""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from app.models.generations import SourceGeneration  # noqa: F401  (registers the referenced table)
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Derivation(Base):
    __tablename__ = "derivations"
    __table_args__ = (UniqueConstraint("generation_id", "stage", "processing_version", "input_derivation_id",
                                       postgresql_nulls_not_distinct=True),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_generations.id"), index=True)
    stage: Mapped[str] = mapped_column(String(16))
    processing_version: Mapped[str] = mapped_column(String(160))
    # The upstream derivation this stage consumed, e.g. the entity set events refer to.
    input_derivation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("derivations.id"))
    status: Mapped[str] = mapped_column(String(16), default="running")
    # Each claim increments it; only the latest claim may publish, so redelivery cannot duplicate rows.
    attempt: Mapped[int] = mapped_column(default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    # Counts of rejected model items by reason; never their text.
    rejections: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_generations.id"), index=True)
    derivation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("derivations.id"), index=True)
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
