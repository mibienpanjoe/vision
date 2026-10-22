"""Reserve one immutable, owned specification and make at most one charged provider call for it."""

import hashlib
import json
import re
import time
import uuid
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.security import owned_object
from app.core.storage import private_renders
from app.db.session import configured_engine
from app.models.access import Principal
from app.models.renders import RenderJob
from app.models.visualizations import Visualization
from app.providers.images import (
    AcceptanceUnknown,
    RenderRejected,
    configured_policy,
    image_adapter,
)
from app.schemas.render import RenderView
from app.services.dispatch import dispatch_renders
from app.services.ingestion.jobs import job_lock
from app.services.visualization import history
from app.services.visualization.refinement import require_current_inputs
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reserve(db, actor, work_id, visualization_id, body, key):
    history.owned(db, actor, work_id, visualization_id)
    # Serialize an owner's reservations so concurrent requests cannot exceed the cap.
    db.scalar(select(Principal.id).where(Principal.id == actor.owner_id).with_for_update())
    digest = fingerprint(body.model_dump(mode="json"))
    prior = db.scalar(select(RenderJob).where(RenderJob.owner_id == actor.owner_id,
        RenderJob.visualization_id == visualization_id, RenderJob.idempotency_key == key))
    if prior is not None:
        if prior.request_hash != digest:
            raise history.conflict()
        return RenderView.from_job(prior)
    policy = configured_policy()
    if policy is None:
        raise PublicError(503, "RENDER_NOT_CONFIGURED", "Image rendering is not configured.")
    visualization = db.scalar(select(Visualization).where(Visualization.id == visualization_id)
        .with_for_update().execution_options(populate_existing=True))
    if visualization.revision != body.specification_revision:
        raise PublicError(409, "SPECIFICATION_CHANGED", "Specification changed. Reload its current revision.")
    spec = history.view(db, visualization).result.data
    require_current_inputs(db, actor, work_id, spec)
    reserved = db.scalar(select(func.count()).select_from(RenderJob).where(RenderJob.owner_id == actor.owner_id))
    if reserved >= policy.max_reservations_per_owner:
        raise PublicError(429, "RENDER_LIMIT", "The configured image-render limit has been reached.")
    snapshot = spec.model_dump(mode="json")
    job = RenderJob(owner_id=actor.owner_id, work_id=work_id, visualization_id=visualization_id,
        specification_revision=body.specification_revision, specification=snapshot,
        specification_sha256=fingerprint(snapshot), request_hash=digest, idempotency_key=key,
        provider=policy.provider, model=policy.model)
    db.add(job)
    db.commit()
    # Intent is already committed; a failed enqueue stays pending for `make dispatch`.
    dispatch_renders(db.get_bind(), job.id)
    db.refresh(job)
    return RenderView.from_job(job)


def owned(db, actor, work_id, job_id):
    job = owned_object(db, RenderJob, job_id, actor)
    if job.work_id != work_id:
        raise history.not_found()
    return job


def cancel(db, actor, work_id, job_id, match, key):
    owned(db, actor, work_id, job_id)
    job = db.scalar(select(RenderJob).where(RenderJob.id == job_id).with_for_update()
                    .execution_options(populate_existing=True))
    if match is None:
        raise PublicError(428, "REVISION_REQUIRED", "A current revision is required.")
    if not re.fullmatch(r'"[1-9][0-9]*"', match):
        raise PublicError(412, "REVISION_CONFLICT", "Render changed. Reload its current state.")
    expected = int(match[1:-1])
    if job.cancel_key == key:
        if job.cancel_expected != expected:
            raise history.conflict()
        return RenderView.model_validate_json(json.dumps(job.cancel_result))
    if job.revision != expected:
        raise PublicError(412, "REVISION_CONFLICT", "Render changed. Reload its current state.")
    if job.status not in {"queued", "running"} or job.cancel_requested:
        raise PublicError(409, "RENDER_STATE", "This render cannot be cancelled.")
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
    job.revision += 1
    job.cancel_key, job.cancel_expected = key, expected
    response = RenderView.from_job(job)
    job.cancel_result = response.model_dump(mode="json")
    db.commit()
    return response


def execute_render(job_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with job_lock(engine, uuid.UUID(job_id)) as acquired:
            if acquired:
                run_render(engine, uuid.UUID(job_id))
    finally:
        engine.dispose()


def locked(db, job_id):
    return db.scalar(select(RenderJob).where(RenderJob.id == job_id).with_for_update())


def settle(job, status, error=None):
    job.status, job.error_code, job.completed_at = status, error, datetime.now(UTC)
    job.revision += 1


def store(data):
    with private_renders().create() as lease:
        try:
            lease.write(data)
            lease.finish()
        except BaseException:
            lease.discard()
            raise
    return lease.reference


def run_render(engine, job_id):
    with Session(engine) as db, db.begin():
        job = locked(db, job_id)
        if job is None or job.status not in {"queued", "running"}:
            return
        if job.status == "running":
            # An earlier claim may have reached the provider; a charged call is never repeated.
            settle(job, "acceptance_unknown", "RENDER_INTERRUPTED")
            return
        adapter = image_adapter()
        if adapter is None or (adapter.provider, adapter.model) != (job.provider, job.model):
            settle(job, "failed", "RENDER_NOT_CONFIGURED")
            return
        prompt = job.specification["generation"]["prompt"]
        job.status, job.started_at, job.revision = "running", datetime.now(UTC), job.revision + 1
        job.settings = {**adapter.settings, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    started, status, error, output, usage = time.monotonic(), "succeeded", None, None, None
    try:
        image = adapter.generate(prompt)
    except AcceptanceUnknown:
        status, error = "acceptance_unknown", "PROVIDER_ACCEPTANCE_UNKNOWN"
    except RenderRejected as rejected:
        status, error = "failed", rejected.code
    else:
        usage = image.usage
        try:
            output = (store(image.data), hashlib.sha256(image.data).hexdigest(), image.media_type, len(image.data))
        except (OSError, ValueError):
            # The provider accepted and charged this call, but its pixels were not kept.
            status, error = "failed", "RENDER_STORAGE_FAILED"
    with Session(engine) as db, db.begin():
        job = locked(db, job_id)
        settle(job, status, error)
        job.duration_ms, job.usage = int((time.monotonic() - started) * 1000), usage
        if output:
            job.output_reference, job.output_sha256, job.output_media_type, job.output_bytes = output


def recover_renders(engine) -> int:
    """Settle claims whose worker died; whether the provider was called is unknown."""
    recovered = 0
    with Session(engine) as db:
        ids = list(db.scalars(select(RenderJob.id).where(RenderJob.status == "running").limit(50)))
    for job_id in ids:
        with job_lock(engine, job_id) as acquired:
            if not acquired:
                continue
            with Session(engine) as db, db.begin():
                job = locked(db, job_id)
                if job.status == "running":
                    settle(job, "acceptance_unknown", "RENDER_INTERRUPTED")
                    recovered += 1
    return recovered
