"""Each immutable visualization revision retains its own request."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("visualization_revisions", sa.Column("request", JSONB(), nullable=True))
    op.execute("UPDATE visualization_revisions r SET request = v.request || jsonb_build_object("
               "'style', r.result #> '{data,generation,style}', "
               "'creative_mode', r.result #> '{data,scope,creative_mode}') "
               "FROM visualizations v WHERE v.id = r.visualization_id")
    op.alter_column("visualization_revisions", "request", nullable=False)


def downgrade():
    op.drop_column("visualization_revisions", "request")
