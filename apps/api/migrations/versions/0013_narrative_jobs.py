"""Durable narrative extraction jobs, one per source generation."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("narrative_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("generation_id", sa.Uuid(), sa.ForeignKey("source_generations.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_table("narrative_jobs")
