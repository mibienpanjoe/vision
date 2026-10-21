"""Scope of query-time derivations (DEC-38 consolidation)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("derivations", sa.Column("scope", JSONB(), nullable=True))


def downgrade():
    op.drop_column("derivations", "scope")
