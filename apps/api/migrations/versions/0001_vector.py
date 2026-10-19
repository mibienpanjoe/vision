"""Enable the selected vector extension; no speculative domain tables."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # No CASCADE: refuse to discard dependent data if later migrations remain.
    op.execute("DROP EXTENSION vector")
