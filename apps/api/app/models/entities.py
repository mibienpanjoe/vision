"""Versioned narrative derivations: entities, exact mentions, aliases and relations.

Every row belongs to one derivation of one source generation, so a changed model
or prompt adds a derivation instead of overwriting an earlier one. Ambiguous
mentions keep their candidates and no resolved identity.
"""

import uuid

from app.models.access import Base
from app.models.model_runs import Derivation, ModelRun  # noqa: F401  (registers the referenced tables)
from app.models.passages import Passage  # noqa: F401
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(256))


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"), index=True)
    start: Mapped[int]
    end: Mapped[int]
    # Set only when the source supports one identity; otherwise see candidates.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"), index=True)
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))


class MentionCandidate(Base):
    __tablename__ = "mention_candidates"
    mention_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entity_mentions.id"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), primary_key=True)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), index=True)
    label: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16))
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))


class EntityRelation(Base):
    __tablename__ = "entity_relations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    relation: Mapped[str] = mapped_column(String(24))
    object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"))
    start: Mapped[int]
    end: Mapped[int]
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))
