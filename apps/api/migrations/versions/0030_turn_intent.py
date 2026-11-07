"""Durable, versioned conversational intent per turn so redelivery never re-classifies."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversation_turns", sa.Column("intent", JSONB(), nullable=True))


def downgrade():
    op.drop_column("conversation_turns", "intent")
