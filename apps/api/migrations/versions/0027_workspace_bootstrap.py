"""Short-lived initialization receipts; durable access stays in hashed sessions."""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_bootstraps", sa.Column("key_hash", sa.String(64), primary_key=True),
                    sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("principals.id"), nullable=False),
                    sa.Column("replay_until", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_workspace_bootstraps_owner_id", "workspace_bootstraps", ["owner_id"])


def downgrade():
    op.drop_table("workspace_bootstraps")
