"""Render execution: claim, terminal outcome and private output reference per reservation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

COLUMNS = [
    ("started_at", sa.DateTime(timezone=True)),
    ("completed_at", sa.DateTime(timezone=True)),
    ("error_code", sa.String(64)),
    ("settings", JSONB()),
    ("duration_ms", sa.Integer()),
    ("usage", JSONB()),
    ("output_reference", sa.String(32)),
    ("output_sha256", sa.String(64)),
    ("output_media_type", sa.String(32)),
    ("output_bytes", sa.Integer()),
]


def upgrade():
    for name, kind in COLUMNS:
        op.add_column("render_jobs", sa.Column(name, kind))


def downgrade():
    for name, _ in reversed(COLUMNS):
        op.drop_column("render_jobs", name)
