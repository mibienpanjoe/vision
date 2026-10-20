"""Atomic visual claims, their exact evidence, applicable events and recorded conflicts.

A fact is canonical only when explicit, affirmed and presented as fact or memory;
other rows stay visible with their support and modality but never act as canon.
"""

import uuid

from app.models.access import Base
from app.models.events import Event  # noqa: F401  (registers the referenced tables)
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class VisualFact(Base):
    __tablename__ = "visual_facts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), index=True)
    attribute: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(16))
    support: Mapped[str] = mapped_column(String(16))
    modality: Mapped[str] = mapped_column(String(16))
    polarity: Mapped[str] = mapped_column(String(16))
    perspective: Mapped[str | None] = mapped_column(String(256))
    assumption: Mapped[str | None] = mapped_column(String(256))

    @property
    def canonical(self) -> bool:
        return self.support == "explicit" and self.polarity == "affirmed" and self.modality in {"fact", "memory"}


class FactEvidence(Base):
    __tablename__ = "fact_evidence"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_facts.id"), index=True)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))


class FactEvent(Base):
    __tablename__ = "fact_events"
    fact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_facts.id"), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), primary_key=True)


class FactConflict(Base):
    __tablename__ = "fact_conflicts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    fact_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_facts.id"))
    fact_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_facts.id"))
    status: Mapped[str] = mapped_column(String(16), default="unresolved")
