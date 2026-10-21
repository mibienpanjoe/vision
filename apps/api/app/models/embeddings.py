"""Passage vectors of one `index` derivation; the derivation's version names the model, so models never mix."""

import uuid

from app.models.access import Base
from app.models.model_runs import Derivation  # noqa: F401  (registers the referenced table)
from app.models.passages import Passage  # noqa: F401
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

DIMENSION = 768


class PassageEmbedding(Base):
    __tablename__ = "passage_embeddings"
    derivation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("derivations.id"), primary_key=True)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"), primary_key=True)
    embedding = mapped_column(Vector(DIMENSION), nullable=False)
