"""Owner-requested work deletion: immediate invisibility, cancelled processing and a durable tombstone."""

import uuid
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.renders import RenderJob
from app.models.works import Document, IngestionJob, Work, WorkDeletion
from app.schemas.works import WorkDeletionView
from sqlalchemy import select

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
                            expected_revision=document.revision, status="pending", requested_at=now)
    db.add(deletion)
    stop_processing(db, work.id, now)
    db.commit()
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
