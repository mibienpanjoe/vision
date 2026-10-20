"""Events, evidence, participants, temporal anchors and relations; derivation inputs."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def span_columns():
    return [sa.Column("passage_id", sa.Uuid(), sa.ForeignKey("passages.id"), nullable=False),
            sa.Column("start", sa.Integer(), nullable=False),
            sa.Column("end", sa.Integer(), nullable=False),
            sa.Column("model_run_id", sa.Uuid(), sa.ForeignKey("model_runs.id"), nullable=False)]


def upgrade():
    op.add_column("derivations", sa.Column("input_derivation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_derivations_input", "derivations", "derivations", ["input_derivation_id"], ["id"])
    op.drop_constraint("derivations_generation_id_stage_processing_version_key", "derivations", type_="unique")
    op.create_unique_constraint("uq_derivations_identity", "derivations",
                                ["generation_id", "stage", "processing_version", "input_derivation_id"],
                                postgresql_nulls_not_distinct=True)
    op.create_table("events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False))
    op.create_index("ix_events_derivation_id", "events", ["derivation_id"])
    op.create_table("event_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        *span_columns())
    op.create_index("ix_event_evidence_event_id", "event_evidence", ["event_id"])
    op.create_table("event_participants",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id"), primary_key=True))
    op.create_table("temporal_anchors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        *span_columns())
    op.create_index("ix_temporal_anchors_event_id", "temporal_anchors", ["event_id"])
    op.create_table("event_relations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("relation", sa.String(16), nullable=False),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        *span_columns())
    op.create_index("ix_event_relations_derivation_id", "event_relations", ["derivation_id"])


def downgrade():
    for table in ("event_relations", "temporal_anchors", "event_participants", "event_evidence", "events"):
        op.drop_table(table)
    op.drop_constraint("uq_derivations_identity", "derivations", type_="unique")
    # Dependent-stage derivations cannot be represented without their input column.
    op.execute("DELETE FROM model_runs WHERE derivation_id IN (SELECT id FROM derivations WHERE input_derivation_id IS NOT NULL)")
    op.execute("DELETE FROM derivations WHERE input_derivation_id IS NOT NULL")
    op.create_unique_constraint("derivations_generation_id_stage_processing_version_key", "derivations",
                                ["generation_id", "stage", "processing_version"])
    op.drop_constraint("fk_derivations_input", "derivations", type_="foreignkey")
    op.drop_column("derivations", "input_derivation_id")
