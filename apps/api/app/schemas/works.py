import uuid
from datetime import datetime
from typing import Literal

from app.schemas.base import ContractModel
from pydantic import Field, field_validator


class UploadMetadata(ContractModel):
    title: str = Field(min_length=1, max_length=256)
    format: Literal["txt", "md", "pdf", "epub"]

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
    format: Literal["txt", "md", "pdf", "epub"]
    byte_count: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    current_parser_revision: str | None


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


class GenerationView(ContractModel):
    id: uuid.UUID
    ordinal: int = Field(ge=1)
    parser_revision: str
    status: Literal["building", "available", "failed", "cancelled"]
    current: bool
    parsed: bool
    narrative_ready: bool
    narrative_status: Literal["not_started", "queued", "running", "succeeded", "failed"]
    narrative_error: str | None = Field(max_length=64, description="Safe error code of the last narrative attempt")
    search_ready: bool
    job_id: uuid.UUID
    warnings: list[str]


class GenerationPage(ContractModel):
    items: list[GenerationView]


class ChapterNumber(ContractModel):
    id: uuid.UUID
    ordinal: int = Field(ge=1)


class ChapterPage(ContractModel):
    document_revision_id: uuid.UUID
    generation_id: uuid.UUID
    parser_revision: str
    items: list[ChapterNumber] = Field(max_length=100)
    next_after: int | None


class WorkDeletionView(ContractModel):
    work_id: uuid.UUID
    status: Literal["pending", "purging", "completed"]
    requested_at: datetime
    completed_at: datetime | None
