"""Local pointers to likely description spans (DEC-38); they rank evidence and are never facts."""

import uuid

from app.models.access import Base
from app.models.entities import Entity  # noqa: F401  (registers the referenced tables)
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class AppearanceCandidate(Base):
    __tablename__ = "appearance_candidates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    cues: Mapped[str] = mapped_column(String(256))


class AppearanceSubject(Base):
    """An entity mentioned (by name or resolved reference) inside the candidate span."""
    __tablename__ = "appearance_subjects"
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("appearance_candidates.id"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), primary_key=True)
