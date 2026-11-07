"""Owned conversation resources; server-issued IDs never come from model output."""
import uuid
from datetime import datetime
from typing import Literal

from app.schemas.appearance_variants import AppearanceVariant
from app.schemas.base import ContractModel
from app.schemas.render import RenderView
from app.schemas.retrieval import Id
from app.schemas.visualization import VisualizationResult, VisualizationView
from pydantic import Field, field_validator, model_validator

TurnStatus = Literal["queued", "waiting_for_book", "resolving", "retrieving", "composing", "verifying", "succeeded", "needs_context", "insufficient_evidence", "failed", "superseded", "cancelled"]


class ConversationCreate(ContractModel):
    work_id: Id
    title: str = Field(default="New conversation", min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def title_text(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid title")
        return value.strip()


class TurnCreate(ContractModel):
    text: str = Field(min_length=1, max_length=4000)
    choice: str | None = Field(default=None, pattern=r"^choice:[0-9]{1,3}$",
                               description="A server-issued ref from the previous turn's open choices")

    @field_validator("text")
    @classmethod
    def meaningful(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Invalid message")
        return value


class VariantSelection(ContractModel):
    variant_id: str = Field(pattern=r"^variant:[0-9a-f]{16}$")
    card_revision: int = Field(ge=1, description="The card revision the variant was issued for")


class RenderRequest(ContractModel):
    card_revision: int = Field(ge=1, description="The active card revision to render; older revisions conflict")


class ConversationRender(ContractModel):
    card_revision: int = Field(ge=1, description="The prompt version this image belongs to")
    render: RenderView


class ConversationRenderPage(ContractModel):
    current_card_revision: int | None = Field(ge=1)
    items: list[ConversationRender] = Field(max_length=20, description="Newest first")


class PreparationRetry(ContractModel):
    pass


class TurnCancel(ContractModel):
    pass


class TurnView(ContractModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    status: TurnStatus
    dispatch_pending: bool
    error_code: str | None
    result: VisualizationResult | None
    card_revision: int | None = Field(ge=1)
    created_at: datetime
    completed_at: datetime | None


class PromptCardView(ContractModel):
    id: uuid.UUID
    revision: int = Field(ge=1)
    generation_id: uuid.UUID
    prompt: str
    specification: VisualizationView
    variants: list[AppearanceVariant] = Field(default_factory=list, max_length=3)
    created_at: datetime

    @model_validator(mode="after")
    def exact_specification(self):
        if self.prompt != self.specification.result.data.generation.prompt or self.generation_id != self.specification.result.data.scope.generation_id:
            raise ValueError("Card must retain its exact specification")
        return self


class ConversationSummary(ContractModel):
    id: uuid.UUID
    work_id: uuid.UUID
    work_title: str
    title: str
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class ConversationView(ConversationSummary):
    last_sequence: int = Field(ge=0)
    active_turn: TurnView | None
    card: PromptCardView | None


class ConversationPage(ContractModel):
    items: list[ConversationSummary] = Field(max_length=50)
    next_cursor: uuid.UUID | None


class ConversationMessageView(ContractModel):
    id: uuid.UUID
    turn_id: uuid.UUID
    sequence: int = Field(ge=1)
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)
    created_at: datetime


class PromptCardSummary(ContractModel):
    revision: int = Field(ge=1)
    current: bool
    prompt: str
    resolved_moment: str | None
    style: str | None
    created_at: datetime


class PromptCardHistory(ContractModel):
    items: list[PromptCardSummary] = Field(max_length=50, description="Newest first; earlier versions are immutable and historical")


class ConversationMessagePage(ContractModel):
    items: list[ConversationMessageView] = Field(max_length=50)
    next_after: int | None = Field(ge=1)
