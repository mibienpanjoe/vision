import uuid
from typing import Annotated, Literal

from app.schemas.base import ContractModel
from pydantic import Field, model_validator

Phrase = Annotated[str, Field(min_length=1, max_length=256)]


class AgeMoment(ContractModel):
    """A story-time age of the subject; never a source position."""
    kind: Literal["age"]
    years: int = Field(ge=0, le=200)


class PhraseMoment(ContractModel):
    """A story-time phrase such as "after the war", anchored by consolidation against cited text."""
    kind: Literal["phrase"]
    text: Phrase


Moment = Annotated[AgeMoment | PhraseMoment, Field(discriminator="kind")]


class VisualizationRequest(ContractModel):
    query: str | None = Field(default=None, min_length=1, max_length=1000)
    entity_id: uuid.UUID | None = None
    moment: Moment | None = None
    context: Phrase | None = Field(default=None, description="Scene context such as \"at home\"")
    through_chapter_id: uuid.UUID | None = Field(default=None, description="Reading cutoff; null means the whole book")
    creative_mode: Literal["canon_first", "interpretation"] = "canon_first"
    style: Phrase | None = None

    @model_validator(mode="after")
    def check_subject(self):
        if self.query is None and self.entity_id is None:
            raise ValueError("A query or an entity is required")
        return self
