"""Owner workload bounds. Values are calibrated by measurement; the environment override serves operators and tests."""

import os
import uuid

from app.core.errors import PublicError
from app.models.access import Principal
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import Document, IngestionJob, Work
from sqlalchemy import exists, func, or_, select

ACTIVE = ("queued", "running")


def max_active_works() -> int:
    return int(os.environ.get("VISION_MAX_ACTIVE_WORKS", "3"))


def require_capacity(db, owner_id: uuid.UUID, work_id: uuid.UUID | None = None) -> None:
    """Refuse work that would make more of an owner's works parse or extract at once than the cap allows.

    The owner row lock serializes concurrent requests; it is held until the caller commits. A work that is
    already active does not count against itself.
    """
    db.scalar(select(Principal.id).where(Principal.id == owner_id).with_for_update())
    parsing = exists().where(IngestionJob.document_id == Document.id, IngestionJob.status.in_(ACTIVE))
    extracting = exists().where(NarrativeJob.generation_id == SourceGeneration.id,
                                SourceGeneration.document_id == Document.id, NarrativeJob.status.in_(ACTIVE))
    query = (select(func.count(func.distinct(Work.id))).join(Document, Document.work_id == Work.id)
             .where(Work.owner_id == owner_id, or_(parsing, extracting)))
    if work_id is not None:
        query = query.where(Work.id != work_id)
    if db.scalar(query) >= max_active_works():
        raise PublicError(429, "RESOURCE_LIMIT", "Too many books are still processing. Try again when one finishes.",
                          True)
