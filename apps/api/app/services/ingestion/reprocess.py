"""Owned source rebuilds as new generations; publication never rewrites old passages."""

from app.core.errors import PublicError
from app.core.limits import require_capacity
from app.core.security import owned_object
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import Document, IngestionJob, Work
from app.schemas.works import GenerationPage, GenerationView
from app.services.dispatch import dispatch_ingestions
from app.services.ingestion.adapters import REVISIONS
from sqlalchemy import func, select

STATUS = {"queued": "building", "running": "building", "succeeded": "available",
          "failed": "failed", "cancelled": "cancelled"}


def generation_view(generation, job, current_id, narrative=None):
    return GenerationView(id=generation.id, ordinal=generation.ordinal, parser_revision=generation.parser_revision,
                          status=STATUS[job.status], current=generation.id == current_id,
                          parsed=job.status == "succeeded", narrative_ready=generation.narrative_ready_at is not None,
                          narrative_status=narrative.status if narrative else "not_started",
                          narrative_error=narrative.error_code if narrative else None,
                          search_ready=generation.search_ready_at is not None, job_id=job.id, warnings=job.warnings)


def owned_document(db, actor, work_id, lock=False):
    owned_object(db, Work, work_id, actor)
    query = select(Document).where(Document.work_id == work_id, Document.revision == 1)
    return db.scalar(query.with_for_update() if lock else query)


def rows(db, document):
    return db.execute(select(SourceGeneration, IngestionJob)
                      .join(IngestionJob, IngestionJob.generation_id == SourceGeneration.id)
                      .where(SourceGeneration.document_id == document.id).order_by(SourceGeneration.ordinal)).all()


def list_generations(db, actor, work_id):
    document = owned_document(db, actor, work_id)
    found = rows(db, document)
    narratives = {n.generation_id: n for n in db.scalars(select(NarrativeJob).where(
        NarrativeJob.generation_id.in_([generation.id for generation, _ in found])))}
    return GenerationPage(items=[generation_view(generation, job, document.current_generation_id,
                                                 narratives.get(generation.id))
                                 for generation, job in found])


def create_generation(db, actor, work_id, key, correlation_id):
    # The document row lock serializes rebuild requests for one source.
    document = owned_document(db, actor, work_id, lock=True)
    existing = rows(db, document)
    for generation, job in existing:
        if generation.idempotency_key == key:
            return generation_view(generation, job, document.current_generation_id)
    if any(job.status in {"queued", "running"} for _, job in existing):
        raise PublicError(409, "GENERATION_IN_PROGRESS", "Another source generation is still being built.")
    revision = REVISIONS[document.format]
    for generation, _ in existing:
        if generation.parser_revision == revision:
            if generation.id == document.current_generation_id:
                raise PublicError(409, "GENERATION_CURRENT", "The current generation already uses this parser.")
            raise PublicError(409, "GENERATION_EXISTS", "A generation for this parser exists; retry its job.")
    require_capacity(db, actor.owner_id, work_id)
    ordinal = (db.scalar(select(func.max(SourceGeneration.ordinal)).where(SourceGeneration.document_id == document.id)) or 0) + 1
    generation = SourceGeneration(document_id=document.id, ordinal=ordinal, parser_revision=revision, idempotency_key=key)
    db.add(generation)
    db.flush()
    job = IngestionJob(document_id=document.id, generation_id=generation.id, processing_version=revision,
                       correlation_id=correlation_id)
    db.add(job)
    db.commit()
    dispatch_ingestions(db.get_bind(), job.id)
    db.refresh(job)
    return generation_view(generation, job, document.current_generation_id)


def publish_generation(db, job):
    """Point the document at the job's generation unless a newer one is current."""
    document = db.scalar(select(Document).where(Document.id == job.document_id).with_for_update())
    generation = db.get(SourceGeneration, job.generation_id)
    current = db.get(SourceGeneration, document.current_generation_id) if document.current_generation_id else None
    if current is None or current.ordinal < generation.ordinal:
        document.current_generation_id = generation.id
