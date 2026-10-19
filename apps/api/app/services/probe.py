"""One bounded transaction for a harmless probe, not an ingestion pipeline."""
import uuid
from datetime import UTC, datetime

from app.core.security import ActorScope, owned_object
from app.db.session import configured_engine
from app.models.access import Principal
from app.models.jobs import Job, JobAttempt
from sqlalchemy import select
from sqlalchemy.orm import Session


def execute_probe(job_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with Session(engine) as db, db.begin():
            job = db.scalar(select(Job).where(Job.id == uuid.UUID(job_id)).with_for_update())
            if job is None or job.status == "succeeded":
                return
            principal = db.get(Principal, job.owner_id)
            if principal is None:
                return
            actor = ActorScope(principal.id, principal.username)
            owned_object(db, Job, job.id, actor)
            started = datetime.now(UTC)
            job.attempts += 1
            job.result = job.value + 1
            job.stage, job.status = "complete", "succeeded"
            db.add(JobAttempt(job_id=job.id, number=job.attempts, stage="probe",
                outcome="succeeded", started_at=started, finished_at=datetime.now(UTC)))
            # Row lock and single commit make duplicate probe delivery harmless.
            # Long-running stages and crash recovery belong to T13, not this probe.
    finally:
        engine.dispose()
