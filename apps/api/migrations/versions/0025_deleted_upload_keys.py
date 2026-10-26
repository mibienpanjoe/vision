"""Keep upload replay protection after physical deletion, without retaining source hashes."""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_deletions", sa.Column("upload_key", sa.String(128)))
    op.execute("UPDATE work_deletions d SET upload_key = w.idempotency_key FROM works w WHERE w.id = d.work_id")
    op.create_unique_constraint("uq_deleted_upload", "work_deletions", ["owner_id", "upload_key"])


def downgrade():
    op.drop_constraint("uq_deleted_upload", "work_deletions", type_="unique")
    op.drop_column("work_deletions", "upload_key")
