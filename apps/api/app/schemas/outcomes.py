"""Shared domain outcome envelope: resolved, needs_context, insufficient_evidence or failed."""

from typing import Annotated, Literal

from app.schemas.base import ContractModel, OpaqueId
from pydantic import BaseModel, Field


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
    field: Literal["subject", "moment", "context"] | None = Field(
        default=None, description="Which request field the choice fills; a moment choice is resubmitted as its label")


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
