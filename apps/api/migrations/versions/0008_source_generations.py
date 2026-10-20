"""Source generations, generation-linked jobs and the published-generation pointer.

Existing documents have exactly one ingestion job; each becomes generation 1 and
a succeeded job's generation becomes current. Downgrade discards generation
history, so it is only safe while each document still has a single job.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("source_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("parser_revision", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("narrative_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("document_id", "ordinal"),
        sa.UniqueConstraint("document_id", "parser_revision"),
        sa.UniqueConstraint("document_id", "idempotency_key"))
    op.create_index("ix_source_generations_document_id", "source_generations", ["document_id"])
    op.add_column("documents", sa.Column("current_generation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_documents_current_generation", "documents", "source_generations",
                          ["current_generation_id"], ["id"])
    op.add_column("ingestion_jobs", sa.Column("generation_id", sa.Uuid(), nullable=True))
    op.execute("""
        INSERT INTO source_generations (id, document_id, ordinal, parser_revision, idempotency_key, created_at)
        SELECT gen_random_uuid(), document_id, 1, processing_version, 'upload', now() FROM ingestion_jobs""")
    op.execute("""
        UPDATE ingestion_jobs j SET generation_id = g.id
        FROM source_generations g WHERE g.document_id = j.document_id""")
    op.execute("""
        UPDATE documents d SET current_generation_id = j.generation_id
        FROM ingestion_jobs j WHERE j.document_id = d.id AND j.status = 'succeeded'""")
    op.alter_column("ingestion_jobs", "generation_id", nullable=False)
    op.create_foreign_key("fk_ingestion_jobs_generation", "ingestion_jobs", "source_generations",
                          ["generation_id"], ["id"])
    op.create_index("ix_ingestion_jobs_generation_id", "ingestion_jobs", ["generation_id"])


def downgrade():
    op.drop_index("ix_ingestion_jobs_generation_id", "ingestion_jobs")
    op.drop_constraint("fk_ingestion_jobs_generation", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "generation_id")
    op.drop_constraint("fk_documents_current_generation", "documents", type_="foreignkey")
    op.drop_column("documents", "current_generation_id")
    op.drop_index("ix_source_generations_document_id", "source_generations")
    op.drop_table("source_generations")
