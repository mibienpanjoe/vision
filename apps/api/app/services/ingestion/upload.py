"""One private original and SQL publication; Redis never owns acceptance state."""

import hashlib
import json

from app.core.errors import PublicError
from app.core.storage import PrivateSources
from app.models.works import Document, IngestionJob, Work
from app.schemas.works import IngestionView, UploadAccepted, WorkView
from app.services.dispatch import dispatch_ingestions
from app.services.ingestion.inputs import validate_text_source
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def document_for(db, work):
    return db.scalar(select(Document).where(Document.work_id == work.id, Document.revision == 1))


def work_view(db, work):
    document = document_for(db, work)
    return WorkView(id=work.id, title=work.title, document_id=document.id,
                    revision=document.revision, format=document.format,
                    byte_count=document.byte_count, sha256=document.sha256)


def ingestion_view(job):
    return IngestionView(id=job.id, document_id=job.document_id, status=job.status,
                         revision=job.revision, cancel_requested=job.cancel_requested,
                         stage=job.stage, correlation_id=job.correlation_id,
                         dispatch_pending=job.dispatched_at is None and job.status == "queued",
                         attempts=job.attempts, error_code=job.error_code, warnings=job.warnings)


def accepted_view(db, work):
    view = work_view(db, work)
    job = db.scalar(select(IngestionJob).where(IngestionJob.document_id == view.document_id))
    return UploadAccepted(work=view, job=ingestion_view(job))


def create_work(db, actor, metadata, data, key, correlation_id):
    validate_text_source(data)
    fingerprint = hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256(json.dumps({**metadata.model_dump(), "sha256": fingerprint}, sort_keys=True).encode()).hexdigest()
    prior = db.scalar(select(Work).where(Work.owner_id == actor.owner_id, Work.idempotency_key == key))
    if prior is not None:
        if prior.request_hash != digest:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for a different upload.")
        return accepted_view(db, prior)
    store = PrivateSources()
    with store.create() as source:
        try:
            source.write(data)
            source.finish()
            work = Work(owner_id=actor.owner_id, title=metadata.title,
                        idempotency_key=key, request_hash=digest)
            db.add(work)
            db.flush()
            document = Document(work_id=work.id, source_ref=source.reference,
                                sha256=fingerprint, format=metadata.format, byte_count=len(data))
            db.add(document)
            db.flush()
            db.add(IngestionJob(document_id=document.id, correlation_id=correlation_id))
            db.flush()
        except IntegrityError:
            db.rollback()
            source.discard()
            prior = db.scalar(select(Work).where(Work.owner_id == actor.owner_id, Work.idempotency_key == key))
            if prior is None:
                raise
            if prior.request_hash != digest:
                raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for a different upload.") from None
            return accepted_view(db, prior)
        except BaseException:
            db.rollback()
            source.discard()
            raise
        # A connection can fail after COMMIT reached PostgreSQL. Keep the file
        # on any uncertain commit; a later reconciliation checks SQL first.
        db.commit()
        job_id = db.scalar(select(IngestionJob.id).where(IngestionJob.document_id == document.id))
        dispatch_ingestions(db.get_bind(), job_id)
        db.expire_all()
        return accepted_view(db, work)
