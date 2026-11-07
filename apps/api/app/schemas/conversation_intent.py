"""Typed conversational intent. Resource references are server-issued refs, never model-invented IDs."""
from typing import ClassVar, Literal

from app.providers.contracts import StructuredOutput
from pydantic import Field, model_validator

INTENT_VERSION = "conversation-intent-v1"
IntentKind = Literal["new_portrayal", "presentation_edit", "moment_edit", "clarification_answer",
                     "source_request", "image_request"]
Text = Field(default=None, min_length=1, max_length=256)


class ConversationIntent(StructuredOutput):
    """Validated output of either the bounded classifier or the deterministic fallback."""
    schema_version: ClassVar[str] = "1.0"
    kind: IntentKind
    query: str | None = Field(default=None, min_length=1, max_length=1000)
    moment: str | None = Text
    context: str | None = Text
    style: str | None = Text
    creative_mode: Literal["canon_first", "interpretation"] | None = None
    keep: list[Literal["attire", "hair", "eyes", "face", "age", "build"]] = Field(default_factory=list, max_length=6)
    ref: str | None = Field(default=None, min_length=1, max_length=64, description="A ref issued in the context block")

    @model_validator(mode="after")
    def complete(self):
        if self.kind == "new_portrayal" and not self.query:
            raise ValueError("A new portrayal needs a self-contained query")
        if self.kind == "clarification_answer" and not self.ref:
            raise ValueError("A clarification answer needs an issued choice ref")
        if self.kind == "presentation_edit" and not (self.style or self.creative_mode or self.keep):
            raise ValueError("A presentation edit needs a style, mode or kept trait")
        if self.kind == "moment_edit" and not (self.query or self.moment or self.context or self.ref):
            raise ValueError("A moment edit needs a moment, context or earlier portrayal ref")
        return self
