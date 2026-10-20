"""Format-specific source anchors such as PDF pages and block boxes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chapters", sa.Column("locator", JSONB(), nullable=True))
    op.add_column("passages", sa.Column("locator", JSONB(), nullable=True))


def downgrade():
    op.drop_column("passages", "locator")
    op.drop_column("chapters", "locator")
