"""Scoped cache of resolved specifications (T32b)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("cached_results",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False),
        sa.Column("work_id", sa.Uuid(), sa.ForeignKey("works.id"), nullable=False),
        sa.Column("generation_id", sa.Uuid(), sa.ForeignKey("source_generations.id"), nullable=False),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("owner_id", "work_id", "generation_id"):
        op.create_index(f"ix_cached_results_{column}", "cached_results", [column])


def downgrade():
    op.drop_table("cached_results")
