"""Atomic visual facts, evidence, applicable events and conflicts."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("visual_facts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("attribute", sa.String(64), nullable=False),
        sa.Column("value", sa.String(256), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("support", sa.String(16), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("polarity", sa.String(16), nullable=False),
        sa.Column("perspective", sa.String(256), nullable=True),
        sa.Column("assumption", sa.String(256), nullable=True))
    op.create_index("ix_visual_facts_derivation_id", "visual_facts", ["derivation_id"])
    op.create_index("ix_visual_facts_subject_id", "visual_facts", ["subject_id"])
    op.create_table("fact_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("fact_id", sa.Uuid(), sa.ForeignKey("visual_facts.id"), nullable=False),
        sa.Column("passage_id", sa.Uuid(), sa.ForeignKey("passages.id"), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("model_run_id", sa.Uuid(), sa.ForeignKey("model_runs.id"), nullable=False))
    op.create_index("ix_fact_evidence_fact_id", "fact_evidence", ["fact_id"])
    op.create_table("fact_events",
        sa.Column("fact_id", sa.Uuid(), sa.ForeignKey("visual_facts.id"), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), primary_key=True))
    op.create_table("fact_conflicts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("fact_a_id", sa.Uuid(), sa.ForeignKey("visual_facts.id"), nullable=False),
        sa.Column("fact_b_id", sa.Uuid(), sa.ForeignKey("visual_facts.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False))
    op.create_index("ix_fact_conflicts_derivation_id", "fact_conflicts", ["derivation_id"])


def downgrade():
    for table in ("fact_conflicts", "fact_events", "fact_evidence", "visual_facts"):
        op.drop_table(table)
