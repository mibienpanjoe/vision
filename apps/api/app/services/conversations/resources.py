"""Bounded owned reads for threads, receipts and exact prompt-card revisions."""
import json

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    PromptCardRevision,
)
from app.models.works import Work
from app.schemas.conversations import (
    ConversationMessagePage,
    ConversationMessageView,
    ConversationPage,
    ConversationSummary,
    ConversationView,
    PromptCardHistory,
    PromptCardSummary,
    PromptCardView,
    TurnView,
)
from app.schemas.visualization import VisualizationResult
from app.services.conversations import store, variants
from app.services.visualization import history
from sqlalchemy import select, tuple_


def turn_view(turn):
    outcome = turn.outcome or {}
    return TurnView(id=turn.id, conversation_id=turn.conversation_id, status=turn.status,
                    dispatch_pending=turn.status in {"queued", "waiting_for_book"} and turn.dispatched_at is None,
                    error_code=turn.error_code, result=VisualizationResult.model_validate_json(json.dumps(outcome["result"])) if outcome.get("result") else None, card_revision=outcome.get("card_revision"),
                    created_at=turn.created_at, completed_at=turn.completed_at)


def summary(db, thread):
    return dict(id=thread.id, work_id=thread.work_id, work_title=db.get(Work, thread.work_id).title,
                title=thread.title, revision=thread.revision, created_at=thread.created_at, updated_at=thread.updated_at)


def card(db, actor, thread, number):
    revision = db.get(PromptCardRevision, (thread.card_id, number))
    if revision is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    specification = history.view(db, history.owned(db, actor, thread.work_id, revision.visualization_id), revision.visualization_revision)
    return PromptCardView(id=revision.card_id, revision=revision.number, generation_id=revision.generation_id,
                          prompt=specification.result.data.generation.prompt, specification=specification,
                          variants=variants.variants(db, revision, specification.result.data), created_at=revision.created_at)


def view(db, actor, thread):
    turn = db.get(ConversationTurn, thread.active_turn_id) if thread.active_turn_id else None
    if turn is not None:
        # Read committed: reload the thread after its turn so a terminal turn never pairs with a pre-publication card.
        db.refresh(turn)
        db.refresh(thread)
        if thread.active_turn_id != turn.id:
            return view(db, actor, thread)
    return ConversationView(**summary(db, thread), last_sequence=thread.next_sequence - 1,
                            active_turn=turn_view(turn) if turn else None,
                            card=card(db, actor, thread, thread.card_revision) if thread.card_revision else None)


def page(db, actor, after, limit, work_id=None):
    query = select(Conversation, Work.title).join(Work, Work.id == Conversation.work_id).where(
        Conversation.owner_id == actor.owner_id, Work.owner_id == actor.owner_id, Work.deleted_at.is_(None))
    if work_id:
        owned_object(db, Work, work_id, actor)
        query = query.where(Conversation.work_id == work_id)
    if after:
        anchor = store.owned(db, actor, after)
        if work_id and anchor.work_id != work_id:
            raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        query = query.where(tuple_(Conversation.created_at, Conversation.id) < (anchor.created_at, anchor.id))
    rows = db.execute(query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit + 1)).all()
    items = [ConversationSummary(id=t.id, work_id=t.work_id, work_title=title, title=t.title, revision=t.revision,
                                  created_at=t.created_at, updated_at=t.updated_at) for t, title in rows[:limit]]
    return ConversationPage(items=items, next_cursor=items[-1].id if len(rows) > limit else None)


def messages(db, actor, conversation_id, after, limit):
    thread = store.owned(db, actor, conversation_id)
    rows = list(db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == thread.id,
                         ConversationMessage.sequence > after).order_by(ConversationMessage.sequence).limit(limit + 1)))
    items = [ConversationMessageView(id=m.id, turn_id=m.turn_id, sequence=m.sequence, role=m.role,
                                     content=m.content, created_at=m.created_at) for m in rows[:limit]]
    return ConversationMessagePage(items=items, next_after=items[-1].sequence if len(rows) > limit else None)


def turn(db, actor, conversation_id, turn_id):
    thread = store.owned(db, actor, conversation_id)
    found = db.scalar(select(ConversationTurn).where(ConversationTurn.id == turn_id, ConversationTurn.conversation_id == thread.id))
    if found is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return turn_view(found)


def card_history(db, actor, thread):
    rows = db.scalars(select(PromptCardRevision).where(PromptCardRevision.card_id == thread.card_id)
                      .order_by(PromptCardRevision.number.desc()).limit(50))
    items = []
    for row in rows:
        spec = history.view(db, history.owned(db, actor, thread.work_id, row.visualization_id), row.visualization_revision).result.data
        items.append(PromptCardSummary(revision=row.number, current=row.number == thread.card_revision, prompt=spec.generation.prompt,
                                       resolved_moment=spec.scope.resolved_moment, style=spec.generation.style, created_at=row.created_at))
    return PromptCardHistory(items=items)
