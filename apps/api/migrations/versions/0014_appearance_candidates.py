"""Appearance-candidate spans and the entities they mention."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("appearance_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("passage_id", sa.Uuid(), sa.ForeignKey("passages.id"), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("cues", sa.String(256), nullable=False))
    op.create_index("ix_appearance_candidates_derivation_id", "appearance_candidates", ["derivation_id"])
    op.create_table("appearance_subjects",
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("appearance_candidates.id"), primary_key=True),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id"), primary_key=True))


def downgrade():
    op.drop_table("appearance_subjects")
    op.drop_table("appearance_candidates")
