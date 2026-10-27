"""Render reservations are consumed independently of deletable book history."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("principals", sa.Column("render_reservations_used", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE principals p SET render_reservations_used = "
               "(SELECT count(*) FROM render_jobs r WHERE r.owner_id = p.id)")
    # Earlier candidate versions erased the only receipt with a purged book. Unknown usage cannot authorize
    # another charged call: conservatively exhaust the DEC-51 cap for those owners, retaining no book data.
    op.execute("UPDATE principals p SET render_reservations_used = greatest(render_reservations_used, 5) "
               "WHERE EXISTS (SELECT 1 FROM work_deletions d WHERE d.owner_id = p.id AND d.status = 'completed')")
    op.create_check_constraint("ck_principals_render_used", "principals", "render_reservations_used >= 0")


def downgrade():
    op.drop_constraint("ck_principals_render_used", "principals", type_="check")
    op.drop_column("principals", "render_reservations_used")
