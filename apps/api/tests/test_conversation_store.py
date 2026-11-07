import uuid

import pytest
from app.core.errors import PublicError
from app.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    PromptCardRevision,
)
from app.services.conversations.store import create, enqueue, publish_card
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_turn_receipts_replay_before_revision_check_and_order_messages(story):
    from app.core.security import ActorScope
    from app.models.access import Principal
    db = story.db
    owner = db.scalar(select(Principal).where(Principal.username == "reader"))
    actor, work_id = ActorScope(owner.id, owner.username), story.plan(None, query="Arthur").work_id
    thread = create(db, actor, work_id, "Arthur", "conversation-key")
    turn = enqueue(db, actor, thread.id, '"1"', "turn-key", {"text": "Show Arthur"}, "test")
    db.commit()
    assert thread.revision == 2 and turn.status == "queued"
    assert enqueue(db, actor, thread.id, '"1"', "turn-key", {"text": "Show Arthur"}, "test").id == turn.id
    with pytest.raises(PublicError) as error:
        enqueue(db, actor, thread.id, '"1"', "another-key", {"text": "Show Mira"}, "test")
    assert error.value.status == 412
    rows = list(db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == thread.id)))
    assert [(row.sequence, row.role, row.content) for row in rows] == [(1, "user", "Show Arthur")]


def test_mixed_owner_work_pointer_is_rejected_by_database(story):
    from app.models.access import Principal
    stranger = story.db.scalar(select(Principal).where(Principal.username == "stranger"))
    work_id = story.plan(None, query="Arthur").work_id
    with Session(story.engine) as db:
        db.add(Conversation(owner_id=stranger.id, work_id=work_id, title="Private", key="key", request_hash="0" * 64))
        with pytest.raises(IntegrityError):
            db.commit()


def test_card_revision_references_exact_stored_specification(api):
    from app.core.security import ActorScope
    from app.models.access import Principal
    from app.models.visualizations import VisualizationRevision
    from app.schemas.retrieval import VisualizationRequest
    from app.services.visualization.history import create as create_visualization
    _, _, work_id, story = api
    db = story.db
    owner = db.scalar(select(Principal).where(Principal.username == "reader"))
    actor = ActorScope(owner.id, owner.username)
    thread = create(db, actor, uuid.UUID(work_id), "Arthur", "conversation")
    turn = enqueue(db, actor, thread.id, '"1"', "turn", {"text": "Show Arthur after the war"}, "test")
    db.commit()
    _, composed = create_visualization(db, actor, uuid.UUID(work_id), VisualizationRequest(query="Arthur", moment={"kind": "phrase", "text": "after the war"}, context="at home"), "visual", "test")
    assert composed.visualization is not None
    card = publish_card(db, turn.id, composed.visualization.id, composed.visualization.revision, "Prompt ready.")
    db.commit()
    assert card.number == 1 and thread.card_id == card.card_id
    assert db.get(ConversationTurn, turn.id).status == "succeeded"
    assert publish_card(db, turn.id, composed.visualization.id, composed.visualization.revision, "Prompt ready.").number == 1
    stored = db.get(VisualizationRevision, (card.visualization_id, card.visualization_revision))
    assert stored.generation_id == card.generation_id
    assert list(db.scalars(select(ConversationMessage.role).where(ConversationMessage.conversation_id == thread.id).order_by(ConversationMessage.sequence))) == ["user", "assistant"]
    db.commit()
    with Session(story.engine) as other:
        other.add(PromptCardRevision(card_id=thread.card_id, number=2, work_id=thread.work_id, owner_id=actor.owner_id,
                                    visualization_id=stored.visualization_id, visualization_revision=999, generation_id=stored.generation_id))
        with pytest.raises(IntegrityError):
            other.commit()


def test_superseded_turn_cannot_replace_the_active_card(story):
    from app.core.security import ActorScope
    from app.models.access import Principal
    db = story.db
    owner = db.scalar(select(Principal).where(Principal.username == "reader"))
    actor = ActorScope(owner.id, owner.username)
    thread = create(db, actor, story.plan(None, query="Arthur").work_id, "Portrait", "thread")
    first = enqueue(db, actor, thread.id, '"1"', "first", {"text": "Arthur"}, "test")
    second = enqueue(db, actor, thread.id, '"2"', "second", {"text": "Mira"}, "test")
    db.commit()
    assert first.status == "superseded" and thread.active_turn_id == second.id
    with pytest.raises(PublicError) as error:
        publish_card(db, first.id, uuid.uuid4(), 1, "Late result.")
    assert error.value.code == "TURN_SUPERSEDED"
    assert thread.card_revision == 0


def test_migration_roundtrip_preserves_existing_book(story):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from app.models.works import Work
    work_id = story.plan(None, query="Arthur").work_id
    story.db.commit()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0028")
    command.upgrade(config, "head")
    with Session(story.engine) as db:
        assert db.get(Work, work_id) is not None
        assert list(db.scalars(select(Conversation))) == []
