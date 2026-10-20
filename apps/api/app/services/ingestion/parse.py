"""Claim, bounded parse and atomic publication with cancellation/recovery guards."""

import hashlib
import uuid
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.storage import PrivateSources
from app.db.session import configured_engine
from app.models.passages import Chapter, Passage
from app.models.works import Document, IngestionAttempt, IngestionJob
from app.services.ingestion.jobs import MAX_ATTEMPTS, finish_attempt, job_lock
from app.services.ingestion.text_adapter import PARSER_REVISION, parse_text
from sqlalchemy import select
from sqlalchemy.orm import Session


def publish_passages(db, document_id, parsed):
    for chapter in parsed.chapters:
        db.add(Chapter(id=uuid.uuid5(document_id, f"{PARSER_REVISION}:chapter:{chapter.ordinal}"),
                       document_id=document_id, parser_revision=PARSER_REVISION,
                       ordinal=chapter.ordinal, title=chapter.title,
                       source_start=chapter.start, source_end=chapter.end))
    db.flush()
    for passage in parsed.passages:
        db.add(Passage(id=uuid.uuid5(document_id, f"{PARSER_REVISION}:passage:{passage.ordinal}"),
            document_id=document_id, parser_revision=PARSER_REVISION, ordinal=passage.ordinal,
            chapter_ordinal=passage.chapter, text=passage.text,
            source_start=passage.start, source_end=passage.end,
            previous_ordinal=passage.ordinal - 1 if passage.ordinal else None,
            next_ordinal=passage.ordinal + 1 if passage.ordinal + 1 < len(parsed.passages) else None))


def execute_ingestion(job_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with job_lock(engine, uuid.UUID(job_id)) as acquired:
            if acquired:
                execute_locked(engine, uuid.UUID(job_id))
    finally:
        engine.dispose()


def execute_locked(engine, job_id):
    with Session(engine) as db, db.begin():
        job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
        if job is None or job.status not in {"queued", "running"}:
            return
        if job.status == "running":
            finish_attempt(db, job, "cancelled" if job.cancel_requested else "abandoned")
        if job.cancel_requested or job.attempts >= MAX_ATTEMPTS:
            job.status = "cancelled" if job.cancel_requested else "failed"
            job.stage = job.status
            job.error_code = None if job.cancel_requested else "ATTEMPTS_EXHAUSTED"
            job.completed_at, job.revision = datetime.now(UTC), job.revision + 1
            return
        document = db.get(Document, job.document_id)
        document_id, source_ref, fingerprint, source_format = document.id, document.source_ref, document.sha256, document.format
        parser_revision = job.processing_version
        job.attempts += 1
        job.status, job.stage, job.revision = "running", "parse", job.revision + 1
        db.add(IngestionAttempt(job_id=job.id, number=job.attempts, outcome="running", started_at=datetime.now(UTC)))
    error_code, parsed = None, None
    try:
        if parser_revision != PARSER_REVISION:
            raise PublicError(422, "UNSUPPORTED_PARSER_VERSION", "Parser revision is not supported.")
        data = PrivateSources().read(source_ref)
        if hashlib.sha256(data).hexdigest() != fingerprint:
            raise PublicError(422, "SOURCE_INTEGRITY", "Original source integrity check failed.")
        parsed = parse_text(data, source_format)
    except PublicError as error:
        error_code = error.code
    except (OSError, ValueError):
        error_code = "SOURCE_STORE_UNAVAILABLE"
    except Exception:
        error_code = "PARSER_FAILURE"
    with Session(engine) as db, db.begin():
        job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
        if job.cancel_requested:
            job.status, job.stage, job.error_code = "cancelled", "cancelled", None
        elif error_code:
            job.status, job.stage, job.error_code = "failed", "failed", error_code
        else:
            publish_passages(db, document_id, parsed)
            job.status, job.stage, job.warnings, job.error_code = "succeeded", "parsed", list(parsed.warnings), None
        finish_attempt(db, job, job.status)
        job.completed_at, job.revision = datetime.now(UTC), job.revision + 1
