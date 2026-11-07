"""Owned threads, SQL turn intent and stable cards pointing at immutable specifications."""
import uuid
from datetime import UTC, datetime

from app.models.access import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


def now():
    return datetime.now(UTC)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(["work_id", "owner_id"], ["works.id", "works.owner_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["active_turn_id", "id"], ["conversation_turns.id", "conversation_turns.conversation_id"], use_alter=True, name="fk_conversation_active_turn", deferrable=True, initially="DEFERRED"),
        UniqueConstraint("owner_id", "key"), UniqueConstraint("card_id", "work_id", "owner_id"),
        CheckConstraint("revision > 0 AND card_revision >= 0 AND next_sequence > 0"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    work_id: Mapped[uuid.UUID] = mapped_column(index=True)
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(160))
    revision: Mapped[int] = mapped_column(default=1)
    next_sequence: Mapped[int] = mapped_column(default=1)
    card_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, unique=True)
    card_revision: Mapped[int] = mapped_column(default=0)
    active_turn_id: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "key"), UniqueConstraint("id", "conversation_id"),
        CheckConstraint("status IN ('queued','waiting_for_book','resolving','retrieving','composing','verifying','succeeded','needs_context','insufficient_evidence','failed','superseded','cancelled')"),
        CheckConstraint("attempts >= 0 AND expected_revision > 0"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    expected_revision: Mapped[int]
    request: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[dict | None] = mapped_column(JSONB)
    intent: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence"), UniqueConstraint("turn_id", "role"),
        ForeignKeyConstraint(["turn_id", "conversation_id"], ["conversation_turns.id", "conversation_turns.conversation_id"], ondelete="CASCADE"),
        CheckConstraint("sequence > 0 AND role IN ('user','assistant') AND length(content) <= 4000"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[uuid.UUID]
    sequence: Mapped[int]
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PromptCardRevision(Base):
    __tablename__ = "prompt_card_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["card_id", "work_id", "owner_id"], ["conversations.card_id", "conversations.work_id", "conversations.owner_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["visualization_id", "work_id", "owner_id"], ["visualizations.id", "visualizations.work_id", "visualizations.owner_id"]),
        ForeignKeyConstraint(["visualization_id", "visualization_revision", "generation_id"], ["visualization_revisions.visualization_id", "visualization_revisions.number", "visualization_revisions.generation_id"]),
        CheckConstraint("number > 0"),
    )
    card_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[uuid.UUID]
    work_id: Mapped[uuid.UUID]
    visualization_id: Mapped[uuid.UUID]
    visualization_revision: Mapped[int]
    generation_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
