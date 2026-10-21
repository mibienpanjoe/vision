"""Stored visual specifications and immutable revisions (T32a)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("visualizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False),
        sa.Column("work_id", sa.Uuid(), sa.ForeignKey("works.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request", JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "work_id", "idempotency_key"))
    op.create_index("ix_visualizations_owner_id", "visualizations", ["owner_id"])
    op.create_index("ix_visualizations_work_id", "visualizations", ["work_id"])
    op.create_table("visualization_revisions",
        sa.Column("visualization_id", sa.Uuid(), sa.ForeignKey("visualizations.id"), primary_key=True),
        sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("generation_id", sa.Uuid(), sa.ForeignKey("source_generations.id"), nullable=False),
        sa.Column("parser_revision", sa.String(32), nullable=False),
        sa.Column("consolidation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("visualization_revisions")
    op.drop_index("ix_visualizations_work_id", table_name="visualizations")
    op.drop_index("ix_visualizations_owner_id", table_name="visualizations")
    op.drop_table("visualizations")
