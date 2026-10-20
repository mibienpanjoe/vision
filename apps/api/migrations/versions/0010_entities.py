"""Versioned entity derivations with exact mentions, aliases and relations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def span_columns():
    return [sa.Column("passage_id", sa.Uuid(), sa.ForeignKey("passages.id"), nullable=False),
            sa.Column("start", sa.Integer(), nullable=False),
            sa.Column("end", sa.Integer(), nullable=False),
            sa.Column("model_run_id", sa.Uuid(), sa.ForeignKey("model_runs.id"), nullable=False)]


def upgrade():
    op.create_table("derivations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("generation_id", sa.Uuid(), sa.ForeignKey("source_generations.id"), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("processing_version", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("rejections", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("generation_id", "stage", "processing_version"))
    op.create_index("ix_derivations_generation_id", "derivations", ["generation_id"])
    op.add_column("model_runs", sa.Column("derivation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_model_runs_derivation", "model_runs", "derivations", ["derivation_id"], ["id"])
    op.create_index("ix_model_runs_derivation_id", "model_runs", ["derivation_id"])
    op.create_table("entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("label", sa.String(256), nullable=False))
    op.create_index("ix_entities_derivation_id", "entities", ["derivation_id"])
    op.create_table("entity_mentions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id"), nullable=True),
        *span_columns())
    for column in ("derivation_id", "passage_id", "entity_id"):
        op.create_index(f"ix_entity_mentions_{column}", "entity_mentions", [column])
    op.create_table("mention_candidates",
        sa.Column("mention_id", sa.Uuid(), sa.ForeignKey("entity_mentions.id"), primary_key=True),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id"), primary_key=True))
    op.create_table("entity_aliases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        *span_columns())
    op.create_index("ix_entity_aliases_entity_id", "entity_aliases", ["entity_id"])
    op.create_table("entity_relations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("derivation_id", sa.Uuid(), sa.ForeignKey("derivations.id"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("relation", sa.String(24), nullable=False),
        sa.Column("object_id", sa.Uuid(), sa.ForeignKey("entities.id"), nullable=False),
        *span_columns())
    op.create_index("ix_entity_relations_derivation_id", "entity_relations", ["derivation_id"])


def downgrade():
    op.drop_table("entity_relations")
    op.drop_table("entity_aliases")
    op.drop_table("mention_candidates")
    op.drop_table("entity_mentions")
    op.drop_table("entities")
    op.drop_index("ix_model_runs_derivation_id", "model_runs")
    op.drop_constraint("fk_model_runs_derivation", "model_runs", type_="foreignkey")
    op.drop_column("model_runs", "derivation_id")
    op.drop_index("ix_derivations_generation_id", "derivations")
    op.drop_table("derivations")
