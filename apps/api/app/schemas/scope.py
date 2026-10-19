from typing import Annotated, Literal

from app.schemas.base import ContractModel, OpaqueId
from pydantic import Field, model_validator


class WholeBook(ContractModel):
    mode: Literal["whole_book"]


class ThroughChapter(ContractModel):
    mode: Literal["through_chapter"]
    chapter_id: OpaqueId


ReadingBoundary = Annotated[WholeBook | ThroughChapter, Field(discriminator="mode")]


class RequestScope(ContractModel):
    work_id: OpaqueId
    document_revision_id: OpaqueId
    generation_id: OpaqueId
    reading_boundary: ReadingBoundary
    story_event_id: OpaqueId | None = None
    creative_mode: Literal["canon_first", "interpretation"]


class SourceSpan(ContractModel):
    document_revision_id: OpaqueId
    passage_id: OpaqueId
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)
    offset_unit: Literal["unicode_code_point"] = "unicode_code_point"

    @model_validator(mode="after")
    def check_length(self):
        if self.end <= self.start or len(self.quote) != self.end - self.start:
            raise ValueError("Span length must match its nonempty code-point quote")
        return self

    def validate_text(self, text: str) -> None:
        # Immutable passage lookup and actor/revision authorization belong to T12.
        if self.end > len(text) or text[self.start:self.end] != self.quote:
            raise ValueError("Source span does not match immutable passage text")
