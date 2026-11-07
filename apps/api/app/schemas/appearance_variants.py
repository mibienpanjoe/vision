"""Server-issued appearance variants of the active card's subject; IDs bind card revision and event."""
import uuid
from typing import Annotated

from app.schemas.base import ContractModel
from app.schemas.evidence import EvidenceSpan
from pydantic import Field

Text = Annotated[str, Field(min_length=1, max_length=256)]


class TraitChange(ContractModel):
    attribute: Text
    before: list[Text] = Field(max_length=8, description="Canonical values on the active card; empty when unknown there")
    after: list[Text] = Field(min_length=1, max_length=8)


class AppearanceVariant(ContractModel):
    id: str = Field(pattern=r"^variant:[0-9a-f]{16}$")
    label: Text
    event_id: uuid.UUID
    changes: list[TraitChange] = Field(min_length=1, max_length=8)
    evidence: list[EvidenceSpan] = Field(min_length=1, max_length=8)
    card_revision: int = Field(ge=1)
    generation_id: uuid.UUID
