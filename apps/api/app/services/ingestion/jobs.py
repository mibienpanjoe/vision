"""Owned conditional mutations, execution leases and interrupted-job recovery."""

from contextlib import contextmanager
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.works import (
    Document,
    IngestionAttempt,
    IngestionJob,
    IngestionMutation,
    Work,
)
from app.services.dispatch import dispatch_ingestions
from app.services.ingestion.upload import ingestion_view
from sqlalchemy import select, text
from sqlalchemy.orm import Session

MAX_ATTEMPTS = 3


@contextmanager
def job_lock(engine, job_id):
    # Dedicated physical connection: invalidation releases even session-level
    # advisory locks after exceptions; no pooled connection retains a lease.
    with engine.connect() as connection:
        try:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": job_id.int % (2**63)})
            connection.commit()
            yield acquired
        finally:
            connection.invalidate()


def finish_attempt(db, job, outcome):
    attempt = db.get(IngestionAttempt, (job.id, job.attempts))
    if attempt is not None and attempt.outcome == "running":
        attempt.outcome, attempt.finished_at = outcome, datetime.now(UTC)


def owned_job(db, actor, work_id, job_id, lock=False):
    owned_object(db, Work, work_id, actor)
    query = select(IngestionJob).join(Document, Document.id == IngestionJob.document_id).where(
        Document.work_id == work_id, IngestionJob.id == job_id)
    if lock:
        query = query.with_for_update(of=IngestionJob)
    job = db.scalar(query)
    if job is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return job


def mutate_job(db, actor, work_id, job_id, action, match, key):
    job = owned_job(db, actor, work_id, job_id, lock=True)
    if match is None:
        raise PublicError(428, "REVISION_REQUIRED", "A current revision is required.")
    try:
        expected = int(match[1:-1]) if match.startswith('"') and match.endswith('"') else -1
    except ValueError:
        expected = -1
    if match != f'"{expected}"':
        expected = -1
    previous = db.get(IngestionMutation, (job.id, key))
    if previous is not None:
        if previous.action != action or previous.expected_revision != expected:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another mutation.")
        return ingestion_view(job)
    if expected != job.revision:
        raise PublicError(412, "REVISION_CONFLICT", "Job changed. Reload its current state.")
    if action == "retry":
        if job.status not in {"failed", "cancelled"}:
            raise PublicError(409, "STATE_CONFLICT", "Job cannot be retried in its current state.")
        if job.attempts >= MAX_ATTEMPTS:
            raise PublicError(429, "ATTEMPTS_EXHAUSTED", "Job attempt budget is exhausted.")
        job.status, job.stage = "queued", "awaiting_parser"
        job.cancel_requested, job.dispatched_at, job.completed_at, job.error_code = False, None, None, None
    else:
        if job.status not in {"queued", "running"}:
            raise PublicError(409, "STATE_CONFLICT", "Job cannot be cancelled in its current state.")
        job.cancel_requested = True
        if job.status == "queued":
            job.status, job.stage, job.completed_at = "cancelled", "cancelled", datetime.now(UTC)
    job.revision += 1
    db.add(IngestionMutation(job_id=job.id, key=key, action=action, expected_revision=expected))
    db.commit()
    if action == "retry":
        dispatch_ingestions(db.get_bind(), job.id)
        db.expire_all()
    return ingestion_view(job)


def recover_ingestions(engine):
    recovered = 0
    with Session(engine) as db:
        ids = list(db.scalars(select(IngestionJob.id).where(IngestionJob.status == "running").limit(50)))
    for job_id in ids:
        with job_lock(engine, job_id) as acquired:
            if not acquired:
                continue
            with Session(engine) as db, db.begin():
                job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
                if job.status != "running":
                    continue
                finish_attempt(db, job, "cancelled" if job.cancel_requested else "abandoned")
                if job.cancel_requested:
                    job.status, job.stage = "cancelled", "cancelled"
                    job.completed_at = datetime.now(UTC)
                elif job.attempts >= MAX_ATTEMPTS:
                    job.status, job.stage, job.error_code = "failed", "failed", "ATTEMPTS_EXHAUSTED"
                    job.completed_at = datetime.now(UTC)
                else:
                    job.status, job.stage, job.dispatched_at = "queued", "awaiting_parser", None
                job.revision += 1
                recovered += 1
    return recovered
