"""Private logical works, immutable originals and durable ingestion intent."""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
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


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    processing_version: Mapped[str] = mapped_column(String(32), default="text-v1")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(32), default="awaiting_parser")
    correlation_id: Mapped[str] = mapped_column(String(128))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
