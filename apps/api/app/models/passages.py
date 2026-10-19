"""Immutable, parser-versioned source slices and explicit chapter anchors."""

import uuid

from app.models.access import Base
from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[uuid.UUID] = mapped_column(unique=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    parser_revision: Mapped[str] = mapped_column(String(32), primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int]
    source_end: Mapped[int]


class Passage(Base):
    __tablename__ = "passages"
    __table_args__ = (
        UniqueConstraint("document_id", "parser_revision", "ordinal"),
        ForeignKeyConstraint(["document_id", "parser_revision", "chapter_ordinal"],
                             ["chapters.document_id", "chapters.parser_revision", "chapters.ordinal"]),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    parser_revision: Mapped[str] = mapped_column(String(32))
    normalization_revision: Mapped[str] = mapped_column(String(32), default="none-v1")
    ordinal: Mapped[int]
    chapter_ordinal: Mapped[int | None]
    source_start: Mapped[int]
    source_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    previous_ordinal: Mapped[int | None]
    next_ordinal: Mapped[int | None]
