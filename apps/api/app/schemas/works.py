import uuid
from typing import Literal

from app.schemas.base import ContractModel
from pydantic import Field, field_validator


class UploadMetadata(ContractModel):
    title: str = Field(min_length=1, max_length=256)
    format: Literal["txt", "md", "pdf"]

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid title")
        return value


class WorkView(ContractModel):
    id: uuid.UUID
    title: str
    document_id: uuid.UUID
    revision: int = Field(ge=1)
    format: Literal["txt", "md", "pdf"]
    byte_count: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class LibraryPage(ContractModel):
    items: list[WorkView]
    next_cursor: uuid.UUID | None


class IngestionView(ContractModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    stage: Literal["awaiting_parser", "parse", "parsed", "failed", "cancelled"]
    revision: int = Field(ge=1)
    cancel_requested: bool
    attempts: int = Field(ge=0)
    error_code: str | None
    warnings: list[str]
    dispatch_pending: bool
    correlation_id: str


class UploadAccepted(ContractModel):
    work: WorkView
    job: IngestionView
