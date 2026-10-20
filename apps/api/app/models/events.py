"""Derived events with exact evidence, participants, temporal anchors and stated relations.

Story-time relations are stored as the source states them; source position is
the evidence passage order and is never used as story order.
"""

import uuid

from app.models.access import Base
from app.models.entities import Entity  # noqa: F401  (registers the referenced table)
from app.models.model_runs import Derivation, ModelRun  # noqa: F401
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    label: Mapped[str] = mapped_column(String(256))
    modality: Mapped[str] = mapped_column(String(16))


class EventEvidence(Base):
    __tablename__ = "event_evidence"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), index=True)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))


class EventParticipant(Base):
    __tablename__ = "event_participants"
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), primary_key=True)


class TemporalAnchor(Base):
    __tablename__ = "temporal_anchors"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(64))
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))


class EventRelation(Base):
    __tablename__ = "event_relations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    relation: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))
