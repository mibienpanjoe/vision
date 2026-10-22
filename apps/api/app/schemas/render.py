import uuid
from datetime import datetime
from typing import Literal

from app.schemas.base import ContractModel
from pydantic import Field


class RenderCreate(ContractModel):
    specification_revision: int = Field(ge=1)


class RenderCancel(ContractModel):
    pass


class RenderView(ContractModel):
    id: uuid.UUID
    work_id: uuid.UUID
    visualization_id: uuid.UUID
    specification_revision: int
    specification_sha256: str
    provider: str
    model: str
    revision: int
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "acceptance_unknown"]
    cancel_requested: bool
    dispatched: bool
    created_at: datetime

    @classmethod
    def from_job(cls, job):
        return cls(**{name: getattr(job, name) for name in cls.model_fields if name != "dispatched"},
                   dispatched=job.dispatched_at is not None)
