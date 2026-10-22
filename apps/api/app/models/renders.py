import uuid
from datetime import UTC, datetime

from app.models.access import Base
from app.models.visualizations import VisualizationRevision  # noqa: F401
from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class RenderJob(Base):
    __tablename__ = "render_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "visualization_id", "idempotency_key"),
        ForeignKeyConstraint(["visualization_id", "specification_revision"],
                             ["visualization_revisions.visualization_id", "visualization_revisions.number"]),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), index=True)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("works.id"), index=True)
    visualization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visualizations.id"), index=True)
    specification_revision: Mapped[int]
    specification: Mapped[dict] = mapped_column(JSONB)
    specification_sha256: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    cancel_key: Mapped[str | None] = mapped_column(String(128))
    cancel_expected: Mapped[int | None]
    cancel_result: Mapped[dict | None] = mapped_column(JSONB)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
