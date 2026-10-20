"""Revision-safe ingestion mutations and durable execution attempts."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ingestion_jobs", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("ingestion_jobs", sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("ingestion_attempts",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("ingestion_jobs.id"), primary_key=True),
        sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("ingestion_mutations",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("ingestion_jobs.id"), primary_key=True),
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("ingestion_mutations")
    op.drop_table("ingestion_attempts")
    op.drop_column("ingestion_jobs", "cancel_requested")
    op.drop_column("ingestion_jobs", "revision")
