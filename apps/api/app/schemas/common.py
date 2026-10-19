from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.schemas.base import ContractModel, OpaqueId
from app.schemas.scope import RequestScope, SourceSpan


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
    source_span: SourceSpan
    scope: RequestScope
    error: ErrorEnvelope
    span_outcome: SpanResolution
