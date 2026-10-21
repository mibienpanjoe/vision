"""Provider-independent visual specification and the compose outcome envelope (T31).

Canonical and disputed traits always carry evidence spans; inferred traits carry
the reason they are not canonical; creative additions carry none and are never
quotations. Unknowns and exclusions stay visible.
"""

import uuid
from typing import Annotated, Literal

from app.schemas.base import ContractModel
from app.schemas.outcomes import Failed, InsufficientEvidence, NeedsContext
from app.schemas.retrieval import Moment
from app.schemas.scope import SourceSpan
from pydantic import Field, RootModel, model_validator

SPEC_VERSION = "vision-spec-1.0"
Text = Annotated[str, Field(min_length=1, max_length=256)]


class TraitView(ContractModel):
    attribute: Text
    status: Literal["canonical", "disputed", "inferred"]
    values: list[Text] = Field(min_length=1)
    evidence: list[SourceSpan]
    reason: Text | None = Field(default=None, description="Why an inferred trait is not canonical")
    adjudication: Literal["unchecked", "entailed"] = "unchecked"

    @model_validator(mode="after")
    def check_grounding(self):
        if self.status != "inferred" and not self.evidence:
            raise ValueError("Canonical and disputed traits require evidence")
        if self.status == "inferred" and not self.reason:
            raise ValueError("Inferred traits state their reason")
        return self


class EntityRef(ContractModel):
    entity_ids: list[uuid.UUID] = Field(min_length=1)
    kind: Literal["character", "place", "object", "organization"]
    label: Text


class MemberView(ContractModel):
    entity: EntityRef
    role: Literal["subject", "participant", "place", "object"]
    traits: list[TraitView]
    unknown: list[Text] = Field(description="Core traits the eligible text does not establish here")


class ExclusionView(ContractModel):
    label: Text
    reason: Text


class CreativeAddition(ContractModel):
    attribute: Text
    value: Text
    support: Literal["creative"] = "creative"
    reason: Text


class ScopeView(ContractModel):
    generation_id: uuid.UUID
    parser_revision: str
    through_chapter_id: uuid.UUID | None = Field(description="Reading cutoff; null means the whole book")
    moment: Moment | None
    resolved_moment: Text | None = Field(description="The event the text anchors the moment to")
    context: Text | None
    creative_mode: Literal["canon_first", "interpretation"]


class GenerationIntent(ContractModel):
    style: Text | None
    prompt: str = Field(min_length=1, max_length=4_000)
    negative_prompt: str = Field(max_length=2_000)


class VerificationView(ContractModel):
    adjudication: Literal["not_requested", "applied", "unavailable"]
    removed: int = Field(ge=0, description="Facts removed by verification")
    selection: Literal["complete", "compressed", "truncated", "protected_overflow"]


class Lineage(ContractModel):
    consolidation_id: uuid.UUID
    processing: dict[str, str]


class VisualSpecification(ContractModel):
    spec_version: Literal["vision-spec-1.0"]
    lineage: Lineage
    scope: ScopeView
    subject: MemberView
    participants: list[MemberView]
    world: list[MemberView]
    excluded: list[ExclusionView]
    unknown: list[Text]
    creative: list[CreativeAddition]
    generation: GenerationIntent
    verification: VerificationView


class ResolvedSpecification(ContractModel):
    outcome: Literal["resolved"]
    schema_version: Literal["1.0"]
    data: VisualSpecification


VisualizationOutcome = Annotated[ResolvedSpecification | NeedsContext | InsufficientEvidence | Failed,
                                 Field(discriminator="outcome")]


class VisualizationResult(RootModel[VisualizationOutcome]):
    pass
