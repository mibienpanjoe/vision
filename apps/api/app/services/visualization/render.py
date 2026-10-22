"""Reserve one immutable, owned specification; no provider calls occur in this slice."""

import hashlib
import json
import re

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.access import Principal
from app.models.renders import RenderJob
from app.models.visualizations import Visualization
from app.providers.images import configured_policy
from app.schemas.render import RenderView
from app.services.visualization import history
from app.services.visualization.refinement import require_current_inputs
from sqlalchemy import func, select


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
