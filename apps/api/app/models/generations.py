"""Versioned parser output sets for one immutable document revision."""

import uuid
from datetime import UTC, datetime

from app.models.access import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class SourceGeneration(Base):
    __tablename__ = "source_generations"
    __table_args__ = (UniqueConstraint("document_id", "ordinal"), UniqueConstraint("document_id", "parser_revision"),
                      UniqueConstraint("document_id", "idempotency_key"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int]
    parser_revision: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Set by the narrative (T22) and search (T25) stages; parsing alone never sets them.
    narrative_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
