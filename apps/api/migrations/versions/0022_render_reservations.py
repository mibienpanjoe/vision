"""Owned immutable render reservations; provider execution remains disabled pending D5."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("render_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False, index=True),
        sa.Column("work_id", sa.Uuid(), sa.ForeignKey("works.id"), nullable=False, index=True),
        sa.Column("visualization_id", sa.Uuid(), sa.ForeignKey("visualizations.id"), nullable=False, index=True),
        sa.Column("specification_revision", sa.Integer(), nullable=False),
        sa.Column("specification", JSONB(), nullable=False),
        sa.Column("specification_sha256", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("cancel_key", sa.String(128)),
        sa.Column("cancel_expected", sa.Integer()),
        sa.Column("cancel_result", JSONB()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "visualization_id", "idempotency_key"),
        sa.ForeignKeyConstraint(["visualization_id", "specification_revision"],
                                ["visualization_revisions.visualization_id", "visualization_revisions.number"]))


def downgrade():
    op.drop_table("render_jobs")
