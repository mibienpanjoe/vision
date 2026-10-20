"""Immutable text parser outputs and bounded parse outcome metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("chapters",
        sa.Column("id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column("parser_revision", sa.String(32), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False))
    op.create_table("passages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("parser_revision", sa.String(32), nullable=False),
        sa.Column("normalization_revision", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("chapter_ordinal", sa.Integer(), nullable=True),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("previous_ordinal", sa.Integer(), nullable=True),
        sa.Column("next_ordinal", sa.Integer(), nullable=True),
        sa.UniqueConstraint("document_id", "parser_revision", "ordinal"),
        sa.ForeignKeyConstraint(["document_id", "parser_revision", "chapter_ordinal"],
                               ["chapters.document_id", "chapters.parser_revision", "chapters.ordinal"]))
    op.create_index("ix_passages_document_id", "passages", ["document_id"])
    op.add_column("ingestion_jobs", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ingestion_jobs", sa.Column("error_code", sa.String(64), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("warnings", JSONB(), server_default="[]", nullable=False))
    op.add_column("ingestion_jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in ("completed_at", "warnings", "error_code", "attempts"):
        op.drop_column("ingestion_jobs", name)
    op.drop_table("passages")
    op.drop_table("chapters")
