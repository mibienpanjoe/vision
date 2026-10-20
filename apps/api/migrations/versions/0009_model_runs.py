"""Safe provider-call lineage records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("model_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False),
        sa.Column("generation_id", sa.Uuid(), sa.ForeignKey("source_generations.id"), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("input_refs", JSONB(), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False))
    op.create_index("ix_model_runs_owner_id", "model_runs", ["owner_id"])
    op.create_index("ix_model_runs_generation_id", "model_runs", ["generation_id"])


def downgrade():
    op.drop_index("ix_model_runs_generation_id", "model_runs")
    op.drop_index("ix_model_runs_owner_id", "model_runs")
    op.drop_table("model_runs")
