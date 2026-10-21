from typing import Annotated, Literal

from app.schemas.access import LoginRequest, PrincipalView
from app.schemas.base import ContractModel, OpaqueId
from app.schemas.entities import EntityDetail, EntityPage
from app.schemas.evidence import EvidenceRequest, EvidenceView
from app.schemas.jobs import JobView, ProbeRequest
from app.schemas.scope import RequestScope, SourceSpan
from app.schemas.works import (
    IngestionView,
    LibraryPage,
    UploadAccepted,
    UploadMetadata,
    WorkView,
)
from pydantic import BaseModel, ConfigDict, Field, RootModel


class SafeError(ContractModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1, max_length=256)
    retryable: bool
    correlation_id: OpaqueId


class ErrorEnvelope(ContractModel):
    error: SafeError


class Resolved[Payload: BaseModel](ContractModel):
    outcome: Literal["resolved"]
    schema_version: Literal["1.0"]
    data: Payload


class ContextChoice(ContractModel):
    id: OpaqueId
    label: str = Field(min_length=1, max_length=256)


class NeedsContext(ContractModel):
    outcome: Literal["needs_context"]
    schema_version: Literal["1.0"]
    choices: list[ContextChoice] = Field(min_length=1)


class InsufficientEvidence(ContractModel):
    outcome: Literal["insufficient_evidence"]
    schema_version: Literal["1.0"]
    missing: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(min_length=1)


class Failed(ContractModel):
    outcome: Literal["failed"]
    schema_version: Literal["1.0"]
    error: SafeError


# A concrete binding proves the generic envelope without inventing a visual schema.
# T31 specializes Resolved with the actual validated VisualSpecification payload.
SpanOutcome = Annotated[
    Resolved[SourceSpan] | NeedsContext | InsufficientEvidence | Failed,
    Field(discriminator="outcome"),
]


class SpanResolution(RootModel[SpanOutcome]):
    model_config = ConfigDict(strict=True)


class SchemaCatalog(ContractModel):
    """Build-time export root only; this is not an HTTP request/response."""
    login_request: LoginRequest
    principal: PrincipalView
    probe_request: ProbeRequest
    job: JobView
    upload_metadata: UploadMetadata
    upload_accepted: UploadAccepted
    work: WorkView
    library_page: LibraryPage
    ingestion: IngestionView
    evidence_request: EvidenceRequest
    evidence: EvidenceView
    source_span: SourceSpan
    scope: RequestScope
    error: ErrorEnvelope
    span_outcome: SpanResolution
    entity_page: EntityPage
    entity_detail: EntityDetail
