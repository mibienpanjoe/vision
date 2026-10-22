"""Durable idempotent conditional refinement receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("visualization_mutations",
        sa.Column("visualization_id", sa.Uuid(), sa.ForeignKey("visualizations.id"), primary_key=True),
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["visualization_id", "result_revision"],
                                ["visualization_revisions.visualization_id", "visualization_revisions.number"]))


def downgrade():
    op.drop_table("visualization_mutations")
