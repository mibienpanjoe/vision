import uuid
from typing import Literal

from app.schemas.base import ContractModel
from app.schemas.scope import SourceSpan
from pydantic import Field


class NarrativeScope(ContractModel):
    generation_id: uuid.UUID
    parser_revision: str
    through_chapter_id: uuid.UUID | None = Field(description="Reading cutoff; null means the whole book")


class AliasView(ContractModel):
    label: str
    status: Literal["supported", "candidate"]
    span: SourceSpan


class EntitySummary(ContractModel):
    id: uuid.UUID
    kind: Literal["character", "place", "object", "organization"]
    label: str = Field(description="A name used by an eligible mention")
    aliases: list[AliasView]
    mention_count: int = Field(ge=1)


class EntityPage(ContractModel):
    scope: NarrativeScope
    items: list[EntitySummary]


class MentionView(ContractModel):
    span: SourceSpan
    entity_id: uuid.UUID | None = Field(description="Set only when the source supports one identity")
    candidate_ids: list[uuid.UUID]


class RelationView(ContractModel):
    subject_id: uuid.UUID
    relation: str
    object_id: uuid.UUID
    span: SourceSpan


class AnchorView(ContractModel):
    kind: Literal["age", "date", "relative"]
    value: str
    span: SourceSpan


class EventView(ContractModel):
    id: uuid.UUID
    label: str
    modality: str
    evidence: list[SourceSpan]
    participant_ids: list[uuid.UUID]
    anchors: list[AnchorView]


class EventRelationView(ContractModel):
    source_id: uuid.UUID
    relation: Literal["before", "after", "during", "overlaps", "unknown"]
    target_id: uuid.UUID
    span: SourceSpan


class FactView(ContractModel):
    id: uuid.UUID
    attribute: str
    value: str
    kind: Literal["identity", "acquired", "interval", "scene"]
    support: Literal["explicit", "inferred"]
    modality: str
    polarity: Literal["affirmed", "negated"]
    perspective: str | None
    assumption: str | None
    canonical: bool
    evidence: list[SourceSpan]
    event_ids: list[uuid.UUID]


class ConflictView(ContractModel):
    fact_ids: list[uuid.UUID] = Field(min_length=2, max_length=2)
    status: Literal["unresolved"]


class EntityDetail(ContractModel):
    scope: NarrativeScope
    entity: EntitySummary
    mentions: list[MentionView] = Field(max_length=200)
    mentions_truncated: bool
    relations: list[RelationView]
    events: list[EventView]
    event_relations: list[EventRelationView]
    facts: list[FactView]
    conflicts: list[ConflictView]
