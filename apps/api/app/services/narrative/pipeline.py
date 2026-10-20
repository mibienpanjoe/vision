"""Run entities → events → facts for a generation through the worker and publish readiness.

The job is queued in the same transaction that publishes parsed passages. A
generation becomes narrative-ready only when all three derivations succeeded;
any failure, cancellation or crash leaves a visible non-ready state. Stages are
idempotent, so redelivery or recovery reuses succeeded derivations instead of
duplicating claims.

Live extraction sends passage text to the configured gateway, so it runs only
when VISION_NARRATIVE_PROVIDER=live; otherwise the job fails as
PROVIDER_NOT_ENABLED rather than disclosing private books by default.
"""

import os
import uuid
from datetime import UTC, datetime

from app.db.session import configured_engine
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.narrative_jobs import NarrativeJob
from app.providers.contracts import Limits
from app.providers.openai_compatible import ChatGateway
from app.services.ingestion.jobs import job_lock
from app.services.narrative.entities import derive_entities
from app.services.narrative.events import derive_events
from app.services.narrative.visual_facts import derive_visual_facts
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_ATTEMPTS = 3
LIMITS = Limits(timeout_seconds=120, max_output_tokens=8_192)


def narrative_adapter():
    if os.environ.get("VISION_NARRATIVE_PROVIDER") != "live":
        return None
    return ChatGateway.from_environment()


def queue_narrative(db, generation_id, correlation_id) -> NarrativeJob:
    job = db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == generation_id))
    if job is None:
        job = NarrativeJob(generation_id=generation_id, correlation_id=correlation_id, status="queued", stage="queued")
        db.add(job)
        db.flush()
    return job


def execute_narrative(job_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with job_lock(engine, uuid.UUID(job_id)) as acquired:
            if acquired:
                run_locked(engine, uuid.UUID(job_id))
    finally:
        engine.dispose()


def set_stage(engine, job_id, stage):
    with Session(engine) as db, db.begin():
        db.get(NarrativeJob, job_id).stage = stage


def run_locked(engine, job_id):
    with Session(engine) as db, db.begin():
        job = db.scalar(select(NarrativeJob).where(NarrativeJob.id == job_id).with_for_update())
        if job is None or job.status not in {"queued", "running"}:
            return
        if job.attempts >= MAX_ATTEMPTS:
            job.status, job.stage, job.error_code = "failed", "failed", "ATTEMPTS_EXHAUSTED"
            job.completed_at = datetime.now(UTC)
            return
        job.attempts += 1
        job.status, job.error_code, generation_id = "running", None, job.generation_id
    adapter, error = narrative_adapter(), None
    if adapter is None:
        error = "PROVIDER_NOT_ENABLED"
    else:
        try:
            upstream = None
            for stage, derive in (("entities", lambda: derive_entities(engine, generation_id, adapter, LIMITS)),
                                  ("events", lambda: derive_events(engine, generation_id, upstream, adapter, LIMITS)),
                                  ("facts", lambda: derive_visual_facts(engine, generation_id, upstream, adapter, LIMITS))):
                set_stage(engine, job_id, stage)
                upstream = derive()
                with Session(engine) as db:
                    derivation = db.get(Derivation, upstream)
                    if derivation.status != "succeeded":
                        error = derivation.error_code or ("EXTRACTION_CANCELLED" if derivation.status == "cancelled"
                                                          else "EXTRACTION_FAILED")
                        break
        except Exception:
            error = "NARRATIVE_FAILURE"
    with Session(engine) as db, db.begin():
        job = db.scalar(select(NarrativeJob).where(NarrativeJob.id == job_id).with_for_update())
        if error:
            job.status, job.stage, job.error_code = "failed", "failed", error
        else:
            generation = db.scalar(select(SourceGeneration).where(SourceGeneration.id == generation_id).with_for_update())
            generation.narrative_ready_at = generation.narrative_ready_at or datetime.now(UTC)
            job.status, job.stage = "succeeded", "narrative_ready"
        job.completed_at = datetime.now(UTC)


def recover_narratives(engine) -> int:
    """Requeue jobs whose worker died mid-run; the attempt budget still applies."""
    recovered = 0
    with Session(engine) as db:
        ids = list(db.scalars(select(NarrativeJob.id).where(NarrativeJob.status == "running").limit(50)))
    for job_id in ids:
        with job_lock(engine, job_id) as acquired:
            if not acquired:
                continue
            with Session(engine) as db, db.begin():
                job = db.scalar(select(NarrativeJob).where(NarrativeJob.id == job_id).with_for_update())
                if job.status != "running":
                    continue
                if job.attempts >= MAX_ATTEMPTS:
                    job.status, job.stage, job.error_code = "failed", "failed", "ATTEMPTS_EXHAUSTED"
                    job.completed_at = datetime.now(UTC)
                else:
                    job.status, job.dispatched_at = "queued", None
                recovered += 1
    return recovered
