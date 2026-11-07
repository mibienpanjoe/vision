"""Finite conversation context rebuilt from durable state, so followups resolve identically after reload."""
from dataclasses import dataclass, field

from app.models.conversations import (
    ConversationMessage,
    ConversationTurn,
    PromptCardRevision,
)
from app.models.visualizations import VisualizationRevision
from sqlalchemy import select

MESSAGES, MESSAGE_CHARS, PORTRAYALS = 6, 500, 5


@dataclass
class Portrayal:
    ref: str
    card_revision: int
    visualization_id: object
    visualization_revision: int
    subject: str
    entity_id: str
    request: dict
    prompt: str
    canonical: dict[str, list[str]]


@dataclass
class Context:
    current: Portrayal | None
    earlier: list[Portrayal]
    choices: dict[str, dict]
    pending: dict | None
    messages: list[dict] = field(default_factory=list)
    variant: str | None = None  # the moment label of a server-issued variant selection

    def block(self) -> dict:
        """Data for the classifier; message text stays untrusted quoted data."""
        describe = lambda p: {"ref": p.ref, "subject": p.subject,  # noqa: E731
                              "moment": p.request.get("moment"), "context": p.request.get("context"),
                              "style": p.request.get("style"), "prompt": p.prompt[:600]}
        return {"current_portrayal": describe(self.current) if self.current else None,
                "earlier_portrayals": [describe(p) for p in self.earlier],
                "open_choices": [{"ref": ref, "label": c["label"], "field": c.get("field")} for ref, c in self.choices.items()],
                "recent_messages": self.messages}


def portrayal(db, card):
    revision = db.get(VisualizationRevision, (card.visualization_id, card.visualization_revision))
    data = revision.result["data"]
    subject = data["subject"]
    canonical = {}
    for trait in subject["traits"]:
        if trait["status"] == "canonical":
            canonical.setdefault(trait["attribute"], []).extend(trait["values"])
    return Portrayal(f"card:{card.number}", card.number, card.visualization_id, card.visualization_revision,
                     subject["entity"]["label"], subject["entity"]["entity_ids"][0], revision.request or {},
                     data["generation"]["prompt"], canonical)


def build(db, thread, turn) -> Context:
    current, earlier = None, []
    if thread.card_revision:
        cards = list(db.scalars(select(PromptCardRevision).where(PromptCardRevision.card_id == thread.card_id)
                                .order_by(PromptCardRevision.number.desc()).limit(PORTRAYALS * 3)))
        seen = set()
        for card in cards:
            item = portrayal(db, card)
            if current is None:
                current = item
                seen.add(item.visualization_id)
            elif item.visualization_id not in seen and len(earlier) < PORTRAYALS:
                seen.add(item.visualization_id)
                earlier.append(item)
    prior = db.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id == thread.id,
                                                     ConversationTurn.created_at < turn.created_at,
                                                     ConversationTurn.status.notin_(["superseded", "cancelled"]))
                      .order_by(ConversationTurn.created_at.desc()).limit(1))
    choices, pending = {}, None
    if prior and prior.status == "needs_context":
        outcome = prior.outcome or {}
        choices = {f"choice:{index}": choice for index, choice in enumerate(outcome.get("result", {}).get("choices", []))}
        pending = outcome.get("visualization_request")
    rows = list(db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == thread.id,
                                                             ConversationMessage.turn_id != turn.id)
                           .order_by(ConversationMessage.sequence.desc()).limit(MESSAGES)))
    messages = [{"role": row.role, "text": row.content[:MESSAGE_CHARS]} for row in reversed(rows)]
    return Context(current, earlier, choices, pending, messages, turn.request.get("moment") if turn.request.get("variant") else None)
