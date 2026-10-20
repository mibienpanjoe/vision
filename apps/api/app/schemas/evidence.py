import uuid
from typing import Annotated

from app.schemas.base import ContractModel
from app.schemas.scope import ReadingBoundary, SourceSpan
from pydantic import Field, model_validator


class EvidenceSpan(SourceSpan):
    quote: str = Field(min_length=1, max_length=2000)


class EvidenceRequest(ContractModel):
    span: EvidenceSpan
    parser_revision: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    reading_boundary: ReadingBoundary
    context_before: int = Field(default=100, ge=0, le=500)
    context_after: int = Field(default=100, ge=0, le=500)


class EvidenceView(ContractModel):
    span: SourceSpan
    parser_revision: str
    excerpt: str = Field(max_length=3000)
    excerpt_start: int = Field(ge=0)
    highlight_start: int = Field(ge=0)
    highlight_end: int = Field(gt=0)
    original_start: int = Field(ge=0)
    original_end: int = Field(gt=0)
    chapter_id: uuid.UUID | None
    pages: list[Annotated[int, Field(ge=1)]] | None = Field(description="Source pages of the containing passage, when the format has pages")


    @model_validator(mode="after")
    def exact_excerpt(self):
        if (self.highlight_end > len(self.excerpt)
                or self.excerpt[self.highlight_start:self.highlight_end] != self.span.quote
                or self.excerpt_start + self.highlight_start != self.span.start
                or self.excerpt_start + self.highlight_end != self.span.end
                or self.original_end - self.original_start != len(self.span.quote)):
            raise ValueError("Excerpt must preserve the exact source span")
        return self
