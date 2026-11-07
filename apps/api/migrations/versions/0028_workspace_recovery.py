"""Trusted local one-time workspace recovery receipts."""
import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_recoveries", sa.Column("key_hash", sa.String(64), primary_key=True),
                    sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("used_key_hash", sa.String(64)))
    op.create_index("ix_workspace_recoveries_owner_id", "workspace_recoveries", ["owner_id"])


def downgrade():
    op.drop_table("workspace_recoveries")
