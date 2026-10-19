import uuid
from typing import Literal

from app.models.jobs import Job
from app.schemas.base import ContractModel, OpaqueId
from pydantic import Field


class ProbeRequest(ContractModel):
    kind: Literal["probe"] = "probe"
    value: int = Field(default=0, ge=0, le=1000000)


class JobView(ContractModel):
    id: uuid.UUID
    status: Literal["queued", "succeeded"]
    stage: Literal["queued", "complete"]
    attempts: int = Field(ge=0)
    result: int | None
    correlation_id: OpaqueId
    dispatch_pending: bool

    @classmethod
    def from_job(cls, job: Job):
        return cls(id=job.id, status=job.status, stage=job.stage, attempts=job.attempts,
                   result=job.result, correlation_id=job.correlation_id,
                   dispatch_pending=job.dispatched_at is None and job.status == "queued")
