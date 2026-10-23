import hashlib
import json
import uuid
from typing import Annotated

from app.core.errors import PublicError
from app.core.http import BoundedJsonRoute
from app.core.security import ActorScope, current_actor, database_session, owned_object
from app.models.jobs import Job
from app.schemas.jobs import JobView, ProbeRequest
from app.services.dispatch import dispatch_pending
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/jobs", tags=["jobs"], route_class=BoundedJsonRoute)


@router.post("", status_code=202, response_model=JobView)
def create_job(body: ProbeRequest, request: Request,
               key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")],
               actor: Annotated[ActorScope, Depends(current_actor)],
               db: Annotated[Session, Depends(database_session)]):
    digest = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    job = Job(owner_id=actor.owner_id, idempotency_key=key, request_hash=digest,
              value=body.value, correlation_id=request.state.correlation_id)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        job = db.scalar(select(Job).where(Job.owner_id == actor.owner_id, Job.idempotency_key == key))
        if job is None:
            raise
        if job.request_hash != digest:
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for a different request.") from None
    dispatch_pending(request.app.state.engine, job.id)
    db.refresh(job)
    return JobView.from_job(job)


@router.get("/{job_id}", response_model=JobView)
def read_job(job_id: uuid.UUID, actor: Annotated[ActorScope, Depends(current_actor)],
             db: Annotated[Session, Depends(database_session)]):
    return JobView.from_job(owned_object(db, Job, job_id, actor))
