"""Wake saved requests after committed ingestion outcomes; SQL intent survives broker outage."""
import logging
import uuid

from app.core.errors import PublicError
from app.core.limits import require_capacity
from app.models.conversations import ConversationTurn
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import Document, IngestionJob
from app.services.conversations import store
from app.services.conversations.turns import recover_turns
from app.services.dispatch import (
    dispatch_conversations,
    dispatch_ingestions,
    dispatch_narratives,
)
from app.services.ingestion.jobs import prepare_retry
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def preparation_finished(engine, job_id, *, narrative=False):
    try:
        with Session(engine) as db:
            job = db.get(NarrativeJob if narrative else IngestionJob, job_id)
            if job is None or job.status not in {"succeeded", "failed", "cancelled"}:
                return
            work_id = db.scalar(select(Document.work_id).join(SourceGeneration, SourceGeneration.document_id == Document.id)
                                .where(SourceGeneration.id == job.generation_id))
        if work_id is not None:
            while recover_turns(engine, work_id=work_id, waiting_only=True):
                pass
            while dispatch_conversations(engine, work_id=work_id):
                pass
    except SQLAlchemyError:
        # Preparation already committed. Reconciliation reads its durable outcome when storage returns.
        log.warning("Conversation preparation wakeup remains pending.")


FATAL = {"TEXT_LAYER_UNAVAILABLE", "PDF_ENCRYPTED", "PARSER_LIMIT", "UNSUPPORTED_FORMAT", "SOURCE_INTEGRITY", "INVALID_SOURCE", "NO_PASSAGES"}


def retry_preparation(db, actor, conversation_id, match, key, correlation_id):
    thread = store.owned(db, actor, conversation_id, lock=True)
    expected = store.expected_revision(match)
    previous = db.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id == thread.id, ConversationTurn.key == key))
    if previous:
        if previous.expected_revision != expected or previous.request.get("operation") != "retry_preparation":
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another request.")
        return previous
    if expected != thread.revision:
        raise PublicError(412, "REVISION_CONFLICT", "Conversation changed. Reload its current state.")
    prior = db.get(ConversationTurn, thread.active_turn_id) if thread.active_turn_id else None
    if prior is None or prior.status != "failed" or prior.error_code != "BOOK_PREPARATION_FAILED":
        raise PublicError(409, "STATE_CONFLICT", "Book preparation cannot be retried in this state.")
    source = db.scalar(select(IngestionJob).join(SourceGeneration, SourceGeneration.id == IngestionJob.generation_id)
                       .join(Document, Document.id == IngestionJob.document_id).where(Document.work_id == thread.work_id, Document.revision == 1)
                       .order_by(SourceGeneration.ordinal.desc()).limit(1).with_for_update(of=IngestionJob))
    narrative = None
    if source.status == "succeeded":
        narrative = db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == source.generation_id).with_for_update())
    db.scalar(select(Document).where(Document.work_id == thread.work_id, Document.revision == 1).with_for_update())
    latest = db.scalar(select(SourceGeneration.id).join(Document, Document.id == SourceGeneration.document_id)
                       .where(Document.work_id == thread.work_id, Document.revision == 1).order_by(SourceGeneration.ordinal.desc()).limit(1))
    if latest != source.generation_id:
        raise PublicError(409, "SCOPE_CHANGED", "Book preparation changed. Reload the conversation.")
    job = narrative or source
    if job.status not in {"failed", "cancelled"}:
        raise PublicError(409, "STATE_CONFLICT", "Book preparation cannot be retried in this state.")
    if job.error_code in FATAL:
        raise PublicError(409, "PREPARATION_NOT_RETRYABLE", "Attach a supported replacement book to continue.")
    if job.attempts >= 3:
        raise PublicError(429, "ATTEMPTS_EXHAUSTED", "Book preparation exhausted its recovery attempts.")
    if narrative:
        require_capacity(db, actor.owner_id, thread.work_id)
        narrative.status, narrative.stage = "queued", "queued"
        narrative.dispatched_at = narrative.completed_at = narrative.error_code = None
    else:
        prepare_retry(db, actor, thread.work_id, source)
        source.revision += 1
    request = {"text": prior.request["text"], "operation": "retry_preparation", "source_job_id": str(job.id),
               "source_stage": "narrative" if narrative else "ingestion", "generation_id": str(source.generation_id)}
    turn = store.enqueue(db, actor, thread.id, match, key, request, correlation_id, message_text="Retry book preparation.")
    turn.status = "waiting_for_book"
    db.flush()
    return turn


def dispatch_retry(engine, turn):
    source_id = uuid.UUID(turn.request["source_job_id"])
    if turn.request["source_stage"] == "narrative":
        dispatch_narratives(engine, source_id)
    else:
        dispatch_ingestions(engine, source_id)
