"""Passage embeddings per index derivation; exact scans until measurements justify an ANN index."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("passage_embeddings",
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), primary_key=True),
        sa.Column("passage_id", sa.Uuid(), sa.ForeignKey("passages.id"), primary_key=True),
        sa.Column("embedding", Vector(768), nullable=False))


def downgrade():
    op.drop_table("passage_embeddings")
