"""Owner-requested work deletion: immediate invisibility, cancelled processing and a durable tombstone."""

import uuid
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.security import owned_object
from app.core.storage import PrivateSources, private_renders
from app.db.session import configured_engine
from app.models.access import Base
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.renders import RenderJob
from app.models.works import Document, IngestionJob, Work, WorkDeletion
from app.schemas.works import WorkDeletionView
from app.services.dispatch import dispatch_deletions
from app.services.ingestion.jobs import job_lock
from sqlalchemy import delete, false, func, or_, select, text, tuple_, update
from sqlalchemy.orm import Session

ACTIVE = ("queued", "running")


def deletion_view(deletion: WorkDeletion) -> WorkDeletionView:
    return WorkDeletionView(work_id=deletion.work_id, status=deletion.status, requested_at=deletion.requested_at,
                            completed_at=deletion.completed_at)


def request_deletion(db, actor, work_id: uuid.UUID, match: str | None, key: str) -> WorkDeletionView:
    prior = db.scalar(select(WorkDeletion).where(WorkDeletion.work_id == work_id,
                                                 WorkDeletion.owner_id == actor.owner_id))
    if prior is not None:
        # Only the request that deleted the work can replay it; for anyone else the work no longer exists.
        if prior.idempotency_key == key and match == f'"{prior.expected_revision}"':
            return deletion_view(prior)
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    owned_object(db, Work, work_id, actor)
    work = db.scalar(select(Work).where(Work.id == work_id).with_for_update())
    if work.deleted_at is not None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    if match is None:
        raise PublicError(428, "REVISION_REQUIRED", "A current revision is required.")
    document = db.scalar(select(Document).where(Document.work_id == work.id))
    if match != f'"{document.revision}"':
        raise PublicError(412, "REVISION_CONFLICT", "Work changed. Reload its current state.")
    now = datetime.now(UTC)
    work.deleted_at = now
    deletion = WorkDeletion(work_id=work.id, owner_id=actor.owner_id, idempotency_key=key,
                            upload_key=work.idempotency_key, expected_revision=document.revision,
                            status="pending", requested_at=now)
    db.add(deletion)
    stop_processing(db, work.id, now)
    db.commit()
    dispatch_deletions(db.get_bind(), work.id)
    db.refresh(deletion)
    return deletion_view(deletion)


def stop_processing(db, work_id: uuid.UUID, now: datetime) -> None:
    """Queued work is cancelled outright; running work is asked to stop and the purge waits for it."""
    generations = select(SourceGeneration.id).join(Document, Document.id == SourceGeneration.document_id).where(
        Document.work_id == work_id)
    ingestions = select(IngestionJob).join(Document).where(Document.work_id == work_id, IngestionJob.status.in_(ACTIVE))
    for job in db.scalars(ingestions.with_for_update(of=IngestionJob)):
        job.cancel_requested, job.revision = True, job.revision + 1
        if job.status == "queued":
            job.status, job.stage, job.completed_at = "cancelled", "cancelled", now
    for job in db.scalars(select(NarrativeJob).where(NarrativeJob.generation_id.in_(generations),
                                                     NarrativeJob.status == "queued").with_for_update()):
        job.status, job.stage, job.error_code, job.completed_at = "cancelled", "cancelled", "WORK_DELETED", now
    for job in db.scalars(select(RenderJob).where(RenderJob.work_id == work_id, RenderJob.status.in_(ACTIVE))
                          .with_for_update()):
        job.cancel_requested, job.revision = True, job.revision + 1
        if job.status == "queued":
            job.status, job.completed_at = "cancelled", now


class StillRunning(Exception):
    """A job of the work has not stopped yet; the purge is retried later."""


class CleanupUnavailable(Exception):
    """Private cleanup storage is unavailable; retry after it is restored."""


# Tables shared by every work: never reached from one. The tombstone outlives the purge.
GLOBAL = {"principals", "jobs", "job_attempts", "login_sessions", "work_deletions"}
CYCLE = ("documents", "current_generation_id")  # cleared first; the generation's own document_id leads back


def scope(table, work_id, seen=()):
    """Rows reachable from the work through foreign keys, composite keys matched as tuples."""
    if table.name == "works":
        return table.c.id == work_id
    paths = []
    for constraint in table.foreign_key_constraints:
        parent = constraint.referred_table
        columns = list(constraint.columns)
        if parent.name in GLOBAL or parent is table or parent.name in seen or \
                (table.name, columns[0].name) == CYCLE:
            continue
        referred = [element.column for element in constraint.elements]
        paths.append(tuple_(*columns).in_(select(*referred).where(scope(parent, work_id, (*seen, table.name)))))
    return or_(*paths) if paths else false()


def purge_rows(db, work_id: uuid.UUID) -> None:
    db.execute(update(Document).where(Document.work_id == work_id).values(current_generation_id=None))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in GLOBAL and not (predicate := scope(table, work_id)).compare(false()):
            db.execute(delete(table).where(predicate))


def active_jobs(db, work_id: uuid.UUID) -> int:
    generations = select(SourceGeneration.id).join(Document, Document.id == SourceGeneration.document_id).where(
        Document.work_id == work_id)
    return sum(db.scalar(select(func.count()).select_from(model).where(condition, model.status == "running"))
               for model, condition in [
                   (IngestionJob, IngestionJob.document_id.in_(select(Document.id).where(Document.work_id == work_id))),
                   (NarrativeJob, NarrativeJob.generation_id.in_(generations)),
                   (RenderJob, RenderJob.work_id == work_id)])


def execute_purge(work_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with job_lock(engine, uuid.UUID(work_id)) as acquired:
            if acquired:
                purge(engine, uuid.UUID(work_id))
    finally:
        engine.dispose()


def recover_deletions(engine) -> int:
    """Republish unfinished cleanup after a lost message or dead worker; a held purge is left alone."""
    recovered = 0
    with Session(engine) as db:
        ids = list(db.scalars(select(WorkDeletion.work_id).where(WorkDeletion.status != "completed")))
    for work_id in ids:
        with job_lock(engine, work_id) as acquired:
            if acquired:
                with Session(engine) as db, db.begin():
                    deletion = db.get(WorkDeletion, work_id, with_for_update=True)
                    if deletion.status != "completed":
                        deletion.dispatched_at = None
                        recovered += 1
    return recovered


def purge(engine, work_id: uuid.UUID) -> None:
    """Files first, then every row in one transaction: an interruption at any point is safe to retry."""
    with Session(engine) as db, db.begin():
        deletion = db.scalar(select(WorkDeletion).where(WorkDeletion.work_id == work_id).with_for_update())
        if deletion is None or deletion.status == "completed":
            return
        waiting = active_jobs(db, work_id) > 0
        if waiting:
            deletion.dispatched_at = None  # `make dispatch` republishes it if the retries run out
        else:
            deletion.status, deletion.attempts = "purging", deletion.attempts + 1
        sources = list(db.scalars(select(Document.source_ref).where(Document.work_id == work_id)))
        images = list(db.scalars(select(RenderJob.output_reference).where(
            RenderJob.work_id == work_id, RenderJob.output_reference.is_not(None))))
    if waiting:
        raise StillRunning()
    try:
        for store, references in ((PrivateSources(), sources), (private_renders(), images)):
            for reference in references:
                store.path(reference).unlink(missing_ok=True)
    except (OSError, ValueError):
        raise CleanupUnavailable("Private cleanup storage unavailable.") from None
    with Session(engine) as db, db.begin():
        # Retention deletes a whole work, unlike a request-sized API operation. Keep it bounded while
        # allowing foreign-key checks on book-sized tables; SET LOCAL cannot leak into API sessions.
        db.execute(text("SET LOCAL statement_timeout = '60s'"))
        deletion = db.scalar(select(WorkDeletion).where(WorkDeletion.work_id == work_id).with_for_update())
        purge_rows(db, work_id)
        deletion.status, deletion.completed_at = "completed", datetime.now(UTC)
