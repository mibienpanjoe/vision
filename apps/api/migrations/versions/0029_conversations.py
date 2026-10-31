"""Owned conversations and immutable prompt-card revision pointers."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_work_owner", "works", ["id", "owner_id"])
    op.create_unique_constraint("uq_visualization_owner_work", "visualizations", ["id", "work_id", "owner_id"])
    op.create_unique_constraint("uq_visualization_revision_generation", "visualization_revisions", ["visualization_id", "number", "generation_id"])
    op.create_table("conversations",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False), sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("title", sa.String(160), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("next_sequence", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False, unique=True), sa.Column("card_revision", sa.Integer(), nullable=False),
        sa.Column("active_turn_id", sa.Uuid()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_id", "owner_id"], ["works.id", "works.owner_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "key"), sa.UniqueConstraint("card_id", "work_id", "owner_id"),
        sa.CheckConstraint("revision > 0 AND card_revision >= 0 AND next_sequence > 0"))
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    op.create_index("ix_conversations_work_id", "conversations", ["work_id"])
    op.create_table("conversation_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False), sa.Column("request", JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)), sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("outcome", JSONB()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "key"), sa.UniqueConstraint("id", "conversation_id"),
        sa.CheckConstraint("status IN ('queued','waiting_for_book','resolving','retrieving','composing','verifying','succeeded','needs_context','insufficient_evidence','failed','superseded','cancelled')"),
        sa.CheckConstraint("attempts >= 0 AND expected_revision > 0"))
    op.create_index("ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"])
    op.create_foreign_key("fk_conversation_active_turn", "conversations", "conversation_turns", ["active_turn_id", "id"], ["id", "conversation_id"], deferrable=True, initially="DEFERRED")
    op.create_table("conversation_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "sequence"), sa.UniqueConstraint("turn_id", "role"),
        sa.ForeignKeyConstraint(["turn_id", "conversation_id"], ["conversation_turns.id", "conversation_turns.conversation_id"], ondelete="CASCADE"),
        sa.CheckConstraint("sequence > 0 AND role IN ('user','assistant') AND length(content) <= 4000"))
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_table("prompt_card_revisions",
        sa.Column("card_id", sa.Uuid(), primary_key=True), sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False), sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("visualization_id", sa.Uuid(), nullable=False), sa.Column("visualization_revision", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["card_id", "work_id", "owner_id"], ["conversations.card_id", "conversations.work_id", "conversations.owner_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visualization_id", "work_id", "owner_id"], ["visualizations.id", "visualizations.work_id", "visualizations.owner_id"]),
        sa.ForeignKeyConstraint(["visualization_id", "visualization_revision", "generation_id"], ["visualization_revisions.visualization_id", "visualization_revisions.number", "visualization_revisions.generation_id"]),
        sa.CheckConstraint("number > 0"))


def downgrade():
    op.drop_table("prompt_card_revisions")
    op.drop_table("conversation_messages")
    op.drop_constraint("fk_conversation_active_turn", "conversations", type_="foreignkey")
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
    op.drop_constraint("uq_visualization_revision_generation", "visualization_revisions", type_="unique")
    op.drop_constraint("uq_visualization_owner_work", "visualizations", type_="unique")
    op.drop_constraint("uq_work_owner", "works", type_="unique")
