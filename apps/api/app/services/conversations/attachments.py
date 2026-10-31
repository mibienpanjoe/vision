"""Wake saved requests after committed ingestion outcomes; SQL intent survives broker outage."""
import logging

from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import Document, IngestionJob
from app.services.conversations.turns import recover_turns
from app.services.dispatch import dispatch_conversations
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
