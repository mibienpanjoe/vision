"""Stored visual specifications and their immutable revisions.

A revision keeps the full validated result with the generation, parser revision
and consolidation it came from, so its citations stay resolvable after later
extraction or refinement.
"""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from app.models.model_runs import Derivation  # noqa: F401  (registers the referenced tables)
from app.models.works import Work  # noqa: F401
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Visualization(Base):
    __tablename__ = "visualizations"
    __table_args__ = (UniqueConstraint("owner_id", "work_id", "idempotency_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(default=1)  # the current revision number
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class VisualizationRevision(Base):
    __tablename__ = "visualization_revisions"
    visualization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visualizations.id"), primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_generations.id"))
    parser_revision: Mapped[str] = mapped_column(String(32))
    consolidation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CachedResult(Base):
    """A resolved result under its full scope key (see services/reconstruction/cache.py)."""
    __tablename__ = "cached_results"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id"), index=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_generations.id"), index=True)
    scope: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
