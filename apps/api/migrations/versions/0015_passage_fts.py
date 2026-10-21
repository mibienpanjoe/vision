"""English full-text vectors over immutable passage text (DEC-22 first language)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("passages", sa.Column("search", TSVECTOR(), sa.Computed("to_tsvector('english', text)", persisted=True)))
    op.create_index("ix_passages_search", "passages", ["search"], postgresql_using="gin")


def downgrade():
    op.drop_index("ix_passages_search", table_name="passages")
    op.drop_column("passages", "search")
