"""Transactional conversation writes. Callers commit before dispatch or after final publication."""
import hashlib
import json
import re
import uuid

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.access import Principal
from app.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    PromptCardRevision,
    now,
)
from app.models.visualizations import Visualization, VisualizationRevision
from app.models.works import Document, Work
from sqlalchemy import select

TERMINAL = {"succeeded", "needs_context", "insufficient_evidence", "failed", "superseded", "cancelled"}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def owned(db, actor, conversation_id, lock=False):
    query = select(Conversation).join(Work, Work.id == Conversation.work_id).where(
        Conversation.id == conversation_id, Conversation.owner_id == actor.owner_id,
        Work.owner_id == actor.owner_id, Work.deleted_at.is_(None))
    if lock:
        query = query.with_for_update(of=Conversation).execution_options(populate_existing=True)
    found = db.scalar(query)
    if found is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return found


def expected_revision(match):
    if match is None:
        raise PublicError(428, "REVISION_REQUIRED", "A current revision is required.")
    if not re.fullmatch(r'"[1-9][0-9]{0,18}"', match):
        raise PublicError(412, "REVISION_CONFLICT", "Conversation changed. Reload its current state.")
    return int(match[1:-1])


def create(db, actor, work_id, title, key):
    owned_object(db, Work, work_id, actor)
    # Serialize the owner's creation receipts, including simultaneous first submissions.
    db.scalar(select(Principal).where(Principal.id == actor.owner_id).with_for_update())
    digest = fingerprint({"work_id": str(work_id), "title": title})
    previous = db.scalar(select(Conversation).where(Conversation.owner_id == actor.owner_id, Conversation.key == key))
    if previous:
        if previous.request_hash != digest:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another conversation.")
        return previous
    thread = Conversation(owner_id=actor.owner_id, work_id=work_id, title=title, key=key, request_hash=digest)
    db.add(thread)
    db.flush()
    return thread


def message(db, thread, turn, role, content):
    db.add(ConversationMessage(conversation_id=thread.id, turn_id=turn.id,
                               sequence=thread.next_sequence, role=role, content=content))
    thread.next_sequence += 1


def enqueue(db, actor, conversation_id, match, key, request, correlation_id):
    thread = owned(db, actor, conversation_id, lock=True)
    expected = expected_revision(match)
    digest = fingerprint(request)
    previous = db.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id == thread.id, ConversationTurn.key == key))
    if previous:
        if previous.request_hash != digest or previous.expected_revision != expected:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another turn.")
        return previous
    if thread.revision != expected:
        raise PublicError(412, "REVISION_CONFLICT", "Conversation changed. Reload its current state.")
    if thread.active_turn_id:
        prior = db.get(ConversationTurn, thread.active_turn_id)
        if prior.status not in TERMINAL:
            prior.status, prior.completed_at = "superseded", now()
    turn = ConversationTurn(id=uuid.uuid4(), conversation_id=thread.id, key=key, request_hash=digest,
                            expected_revision=expected, request=request, correlation_id=correlation_id)
    db.add(turn)
    db.flush()
    thread.active_turn_id = turn.id
    thread.revision += 1
    thread.updated_at = now()
    message(db, thread, turn, "user", request["text"])
    db.flush()
    return turn


def publish_card(db, turn_id, visualization_id, number, receipt):
    turn = db.get(ConversationTurn, turn_id)
    if turn is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    thread = db.scalar(select(Conversation).where(Conversation.id == turn.conversation_id)
                       .with_for_update().execution_options(populate_existing=True))
    db.refresh(turn)
    if turn.status == "succeeded":
        return db.get(PromptCardRevision, (thread.card_id, turn.outcome["card_revision"]))
    if turn.status in TERMINAL or thread.active_turn_id != turn.id:
        raise PublicError(409, "TURN_SUPERSEDED", "A newer request is active.")
    work = db.get(Work, thread.work_id)
    visualization = db.get(Visualization, visualization_id)
    revision = db.get(VisualizationRevision, (visualization_id, number))
    if (work is None or work.deleted_at is not None or visualization is None or revision is None
            or visualization.owner_id != thread.owner_id or visualization.work_id != thread.work_id):
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    document = db.scalar(select(Document).where(Document.work_id == thread.work_id, Document.revision == 1).with_for_update())
    if document.current_generation_id != revision.generation_id:
        raise PublicError(409, "SCOPE_CHANGED", "The book changed. Create a new request.")
    card = PromptCardRevision(card_id=thread.card_id, number=thread.card_revision + 1, owner_id=thread.owner_id,
                              work_id=thread.work_id, visualization_id=visualization_id,
                              visualization_revision=number, generation_id=revision.generation_id)
    db.add(card)
    thread.card_revision, thread.revision, thread.updated_at = card.number, thread.revision + 1, now()
    message(db, thread, turn, "assistant", receipt)
    turn.status, turn.completed_at, turn.outcome = "succeeded", now(), {"card_revision": card.number}
    db.flush()
    return card
