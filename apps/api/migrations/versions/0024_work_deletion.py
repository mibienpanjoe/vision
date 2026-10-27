"""Work deletion: immediate invisibility and a minimal tombstone that drives and records the purge."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("works", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    # No foreign key to works: the tombstone outlives the row it records. It holds no title, text or hashes.
    op.create_table(
        "work_deletions",
        sa.Column("work_id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("work_deletions")
    op.drop_column("works", "deleted_at")
