"""Durable turn execution: bounded retries and atomic publication guarded by the active thread."""
import uuid
from datetime import timedelta

from app.core.errors import PublicError
from app.core.security import ActorScope
from app.db.session import configured_engine
from app.models.conversations import Conversation, ConversationTurn
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import Document, IngestionJob, Work
from app.schemas.retrieval import VisualizationRequest
from app.services.conversations import resources, store
from app.services.ingestion.jobs import job_lock
from app.services.visualization import history
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

RUNNING = {"resolving", "retrieving", "composing", "verifying"}
MAX_ATTEMPTS = 3


class Superseded(Exception):
    pass


def book_state(db, work_id):
    document = db.scalar(select(Document).where(Document.work_id == work_id, Document.revision == 1))
    generation = db.get(SourceGeneration, document.current_generation_id) if document and document.current_generation_id else None
    if generation and generation.narrative_ready_at and generation.search_ready_at:
        return "ready"
    if document:
        latest = db.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id)
                           .join(SourceGeneration, SourceGeneration.id == IngestionJob.generation_id)
                           .order_by(SourceGeneration.ordinal.desc()).limit(1))
        if latest and latest.status in {"failed", "cancelled"}:
            return "failed"
        if generation:
            job = db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == generation.id))
            if job and job.status == "failed":
                return "failed"
    return "waiting"


def active(db, turn_id):
    turn = db.get(ConversationTurn, turn_id)
    if turn is None:
        raise Superseded()
    thread = db.scalar(select(Conversation).where(Conversation.id == turn.conversation_id)
                       .with_for_update().execution_options(populate_existing=True))
    db.refresh(turn)
    if thread is None or thread.active_turn_id != turn.id or turn.status in store.TERMINAL:
        raise Superseded()
    work = db.get(Work, thread.work_id)
    if work is None or work.deleted_at is not None:
        raise Superseded()
    return thread, turn


def stage(engine, turn_id, status):
    with Session(engine) as db, db.begin():
        _, turn = active(db, turn_id)
        turn.status = status


def finish(db, thread, turn, status, receipt, outcome=None, error_code=None):
    store.message(db, thread, turn, "assistant", receipt)
    turn.status, turn.completed_at, turn.error_code = status, store.now(), error_code
    turn.outcome = outcome or {}
    thread.revision, thread.updated_at = thread.revision + 1, store.now()


def cancel(db, actor, conversation_id, turn_id, match, key):
    thread = store.owned(db, actor, conversation_id, lock=True)
    turn = db.scalar(select(ConversationTurn).where(ConversationTurn.id == turn_id, ConversationTurn.conversation_id == thread.id))
    if turn is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    expected = store.expected_revision(match)
    receipt = {"key": key, "revision": expected}
    previous = (turn.outcome or {}).get("cancellation")
    if previous:
        if previous != receipt:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another cancellation.")
        return resources.turn_view(turn)
    if expected != thread.revision:
        raise PublicError(412, "REVISION_CONFLICT", "Conversation changed. Reload its current state.")
    if turn.status in store.TERMINAL or thread.active_turn_id != turn.id:
        raise PublicError(409, "STATE_CONFLICT", "This request cannot be cancelled.")
    finish(db, thread, turn, "cancelled", "Request cancelled. Your previous prompt is still available.", {"cancellation": receipt})
    db.flush()
    return resources.turn_view(turn)


def execute_turn(turn_id):
    engine = configured_engine()
    if engine is None:
        return
    try:
        turn_id = uuid.UUID(turn_id)
        with job_lock(engine, turn_id) as acquired:
            if acquired:
                execute_claimed(engine, turn_id)
        # Preparation can finish while this turn is committing its waiting state under the lease.
        # Recheck after release so either this handoff or the preparation notification wakes it.
        recover_turns(engine, turn_id=turn_id, waiting_only=True)
        from app.services.dispatch import dispatch_conversations
        dispatch_conversations(engine, turn_id=turn_id)
    finally:
        engine.dispose()


def execute_claimed(engine, turn_id):
    try:
        with Session(engine) as db, db.begin():
            thread, turn = active(db, turn_id)
            state = book_state(db, thread.work_id)
            if state == "waiting":
                turn.status, turn.dispatched_at = "waiting_for_book", None
                return
            if state == "failed":
                finish(db, thread, turn, "failed", "The book could not be prepared. Retry preparation or attach another book.", error_code="BOOK_PREPARATION_FAILED")
                return
            if turn.attempts >= MAX_ATTEMPTS:
                finish(db, thread, turn, "failed", "This request exhausted its recovery attempts. Submit a new request.", error_code="TURN_ATTEMPTS_EXHAUSTED")
                return
            turn.attempts += 1
            turn.status = "resolving"
            actor, work_id, request, correlation = ActorScope(thread.owner_id, "workspace"), thread.work_id, turn.request, turn.correlation_id
        # Q38 replaces this bounded initial-query adapter with durable structured conversational intent.
        if len(request["text"]) > 1000:
            raise PublicError(422, "INTENT_NOT_SUPPORTED", "Use a shorter initial portrayal request.")
        body = VisualizationRequest(query=request["text"])
        with Session(engine) as db:
            _, result = history.create(db, actor, work_id, body, f"turn_{turn_id.hex}", correlation,
                                       progress=lambda value: stage(engine, turn_id, value))
        with Session(engine) as db, db.begin():
            thread, turn = active(db, turn_id)
            if result.visualization:
                store.publish_card(db, turn_id, result.visualization.id, result.visualization.revision, "Your source-grounded prompt is ready.")
            else:
                outcome = result.result.root
                receipt = {"needs_context": "Choose which portrayal you mean.", "insufficient_evidence": "The eligible text does not establish a usable portrayal.",
                           "failed": "This request could not finish. Your previous prompt is still available."}[outcome.outcome]
                finish(db, thread, turn, outcome.outcome, receipt, {"result": result.result.model_dump(mode="json")},
                       outcome.error.code if outcome.outcome == "failed" else None)
    except Superseded:
        return
    except PublicError as error:
        fail(engine, turn_id, error.code)
    except SQLAlchemyError:
        raise  # Leave durable progress for lease-aware recovery after storage returns.
    except Exception:
        fail(engine, turn_id, "TURN_FAILED")


def fail(engine, turn_id, code):
    try:
        with Session(engine) as db, db.begin():
            thread, turn = active(db, turn_id)
            finish(db, thread, turn, "failed", "This request could not finish. Your previous prompt is still available.", error_code=code)
    except Superseded:
        pass


def recover_turns(engine, work_id=None, turn_id=None, waiting_only=False):
    """Recover abandoned leases and wake persisted requests after preparation, never an active worker."""
    recovered = 0
    ready = select(SourceGeneration.id).where(SourceGeneration.narrative_ready_at.is_not(None), SourceGeneration.search_ready_at.is_not(None))
    narrative_failed = select(NarrativeJob.generation_id).where(NarrativeJob.status == "failed")
    latest_parse = select(IngestionJob.status).join(SourceGeneration, SourceGeneration.id == IngestionJob.generation_id).where(
        IngestionJob.document_id == Document.id).order_by(SourceGeneration.ordinal.desc()).limit(1).scalar_subquery()
    wakeable = select(Document.work_id).where(or_(Document.current_generation_id.in_(ready),
        Document.current_generation_id.in_(narrative_failed), latest_parse.in_(["failed", "cancelled"])))
    with Session(engine) as db:
        query = (select(ConversationTurn.id).join(Conversation, Conversation.id == ConversationTurn.conversation_id).where(or_(
            ConversationTurn.status.in_(RUNNING),
            and_(ConversationTurn.status == "waiting_for_book", Conversation.work_id.in_(wakeable)),
            and_(ConversationTurn.status == "queued", ConversationTurn.dispatched_at < store.now() - timedelta(minutes=5))))
            .order_by(ConversationTurn.created_at).limit(50))
        if work_id is not None:
            query = query.where(Conversation.work_id == work_id)
        if turn_id is not None:
            query = query.where(ConversationTurn.id == turn_id)
        if waiting_only:
            query = query.where(ConversationTurn.status == "waiting_for_book")
        ids = list(db.scalars(query))
    for turn_id in ids:
        with job_lock(engine, turn_id) as acquired:
            if not acquired:
                continue
            try:
                with Session(engine) as db, db.begin():
                    thread, turn = active(db, turn_id)
                    if turn.status == "waiting_for_book" and book_state(db, thread.work_id) == "waiting":
                        continue
                    turn.status, turn.dispatched_at = "queued", None
                    recovered += 1
            except Superseded:
                continue
    return recovered
