"""Private logical works, immutable originals and durable ingestion intent."""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from app.models.generations import SourceGeneration  # noqa: F401  (registers the referenced table)
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Set when the owner deletes the work: every route treats it as absent until the purge removes the row.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkDeletion(Base):
    """A minimal tombstone: owner, work ID and lifecycle times only, kept after the purge."""
    __tablename__ = "work_deletions"
    work_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    expected_revision: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("work_id", "revision"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id"), index=True)
    revision: Mapped[int] = mapped_column(default=1)
    source_ref: Mapped[str] = mapped_column(String(32), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(16))
    byte_count: Mapped[int]
    # Published generation; moves only to a higher ordinal under this row's lock.
    current_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_generations.id", use_alter=True, name="fk_documents_current_generation"))


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_generations.id"), index=True)
    revision: Mapped[int] = mapped_column(default=1)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    processing_version: Mapped[str] = mapped_column(String(32), default="text-v1")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(32), default="awaiting_parser")
    correlation_id: Mapped[str] = mapped_column(String(128))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionAttempt(Base):
    __tablename__ = "ingestion_attempts"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    outcome: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionMutation(Base):
    __tablename__ = "ingestion_mutations"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    action: Mapped[str] = mapped_column(String(16))
    expected_revision: Mapped[int]
