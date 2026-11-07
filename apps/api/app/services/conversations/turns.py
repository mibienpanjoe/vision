"""Durable turn execution: bounded retries and atomic publication guarded by the active thread."""
import re
import uuid
from datetime import timedelta

from app.core.errors import PublicError
from app.core.security import ActorScope
from app.db.session import configured_engine
from app.models.conversations import Conversation, ConversationTurn
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.visualizations import Visualization
from app.models.works import Document, IngestionJob, Work
from app.schemas.conversation_intent import INTENT_VERSION, ConversationIntent
from app.schemas.retrieval import VisualizationRequest
from app.schemas.visualization import CanonicalLock, RefinementRequest
from app.services.conversations import context, intent, render_actions, resources, store
from app.services.ingestion.jobs import job_lock
from app.services.visualization import history, refinement
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
            situation = context.build(db, thread, turn)
            chosen = turn.intent
            generation_id = db.scalar(select(Document.current_generation_id).where(Document.work_id == work_id, Document.revision == 1))
        if chosen is None:
            with Session(engine) as db, db.begin():
                proposed, source = intent.classify(db, actor.owner_id, generation_id, situation, request["text"], request.get("choice"))
            with Session(engine) as db, db.begin():
                _, turn = active(db, turn_id)
                turn.intent = turn.intent or {"version": INTENT_VERSION, "source": source, **proposed.model_dump(mode="json")}
                chosen = turn.intent
        route(engine, turn_id, actor, work_id, situation, ConversationIntent.model_validate(
            {k: v for k, v in chosen.items() if k not in {"version", "source"}}), request, correlation)
    except Superseded:
        return
    except PublicError as error:
        fail(engine, turn_id, error.code)
    except SQLAlchemyError:
        raise  # Leave durable progress for lease-aware recovery after storage returns.
    except Exception:
        fail(engine, turn_id, "TURN_FAILED")


RECEIPTS = {"needs_context": "Choose which portrayal you mean.", "insufficient_evidence": "The eligible text does not establish a usable portrayal.",
            "failed": "This request could not finish. Your previous prompt is still available."}


def route(engine, turn_id, actor, work_id, situation, chosen, request, correlation):
    current, key = situation.current, f"turn_{turn_id.hex}"
    if chosen.kind == "image_request" and current is not None:
        # The same card-revision key as the Generate image button: one render per prompt version.
        try:
            with Session(engine) as db:
                thread = store.owned(db, actor, situation_thread(db, turn_id), lock=True)
                made = render_actions.reserve(db, actor, thread, thread.card_revision)
            receipt, status, code = f"Generating an image from prompt version {made.card_revision}.", "succeeded", None
        except PublicError as error:
            receipt, status, code = error.message, "failed", error.code
        with Session(engine) as db, db.begin():
            thread, turn = active(db, turn_id)
            finish(db, thread, turn, status, receipt, {"intent": chosen.kind, "card_revision": thread.card_revision}, code)
        return
    if chosen.kind in {"source_request", "image_request"}:
        receipt = ("Open Sources on the prompt card for the cited passages." if chosen.kind == "source_request"
                   else "Create a prompt first; then ask for an image.")
        with Session(engine) as db, db.begin():
            thread, turn = active(db, turn_id)
            finish(db, thread, turn, "succeeded", receipt, {"intent": chosen.kind, "card_revision": thread.card_revision})
        return
    if chosen.kind == "moment_edit" and chosen.ref:
        earlier = next(p for p in situation.earlier if p.ref == chosen.ref)
        with Session(engine) as db, db.begin():
            store.publish_card(db, turn_id, earlier.visualization_id, earlier.visualization_revision, f"Restored the earlier version ({earlier.subject}).")
        return
    if chosen.kind == "presentation_edit":
        with Session(engine) as db:  # refine commits its own revision and idempotency receipt
            visualization = db.get(Visualization, current.visualization_id)
            mode = chosen.creative_mode or current.request.get("creative_mode", "canon_first")
            locks = [CanonicalLock(entity_id=current.entity_id, attribute=name, value=value)
                     for name in chosen.keep for value in current.canonical.get(name, [])]
            body = RefinementRequest(style=chosen.style or current.request.get("style"), creative_mode=mode, locks=locks)
            refined = refinement.refine(db, actor, work_id, visualization.id, body, f'"{visualization.revision}"', key)
        with Session(engine) as db, db.begin():
            store.publish_card(db, turn_id, refined.id, refined.revision, change_receipt(chosen))
        return
    body, pending = visualization_request(situation, chosen, request)
    with Session(engine) as db:
        _, result = history.create(db, actor, work_id, body, key, correlation,
                                   progress=lambda value: stage(engine, turn_id, value))
    with Session(engine) as db, db.begin():
        thread, turn = active(db, turn_id)
        if result.visualization:
            moment = result.visualization.result.data.scope.resolved_moment
            text = ("Your source-grounded prompt is ready." if current is None or chosen.kind == "new_portrayal"
                    else f"Updated from the book: {moment}." if moment else "Updated from the book.")
            store.publish_card(db, turn_id, result.visualization.id, result.visualization.revision, text)
        else:
            outcome = result.result.root
            finish(db, thread, turn, outcome.outcome, RECEIPTS[outcome.outcome],
                   {"result": result.result.model_dump(mode="json"), "visualization_request": pending},
                   outcome.error.code if outcome.outcome == "failed" else None)


def situation_thread(db, turn_id):
    return db.get(ConversationTurn, turn_id).conversation_id


def change_receipt(chosen):
    """A concise, factual change receipt for a presentation-only edit."""
    style = re.sub(r"^(as|in)\s+(an?\s+)?", "", chosen.style, flags=re.I) if chosen.style else None
    parts = [f"restyled: {style}"] if style else []
    if chosen.creative_mode:
        parts.append("artist's choices allowed for unknowns" if chosen.creative_mode == "interpretation" else "book facts only")
    if chosen.keep:
        parts.append("kept " + ", ".join(chosen.keep))
    return (("; ".join(parts) or "Updated").capitalize() + ". Book facts unchanged.")[:4000]


def visualization_request(situation, chosen, request):
    """Every content change, including wardrobe or scene, goes through full source verification."""
    current = situation.current
    if chosen.kind == "clarification_answer":
        choice = situation.choices[chosen.ref]
        values = dict(situation.pending or {"query": request["text"][:1000]})
        if choice.get("field") == "subject":
            values.update(entity_id=choice["id"], query=None)
        elif choice.get("field") == "moment":
            values["moment"] = {"kind": "phrase", "text": choice["label"]}
        else:
            values["context"] = choice["label"]
    elif chosen.kind == "moment_edit":
        values = {"entity_id": current.entity_id, "query": chosen.query,
                  "moment": {"kind": "phrase", "text": chosen.moment} if chosen.moment else None, "context": chosen.context,
                  "style": current.request.get("style"), "creative_mode": current.request.get("creative_mode", "canon_first")}
    else:
        values = {"query": chosen.query}
    body = VisualizationRequest.model_validate({k: v for k, v in values.items() if v is not None})
    return body, body.model_dump(mode="json")


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
