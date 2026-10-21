"""Event-extraction role: dated/relative events, modality and stated temporal relations.

Earlier chapters' event keys travel as a separate data item so a later passage
can relate to them; that item is derived data, never citable evidence.
"""

from typing import Annotated, Literal

from app.providers.contracts import (
    Limits,
    ProviderRequest,
    SourceItem,
    StructuredOutput,
)
from app.providers.extraction import Key, Label, Quote, Ref
from pydantic import Field

PROMPT_VERSION = "events-v1"
KNOWN_REF = "known-events"
Modality = Literal["fact", "memory", "dream", "rumor", "metaphor", "hypothesis"]
TemporalRelation = Literal["before", "after", "during", "overlaps", "unknown"]
EventKey = Annotated[str, Field(pattern=r"^(k:)?[a-z0-9_-]{1,32}$")]

INSTRUCTIONS = f"""You extract narrative events from numbered book passages.
Return JSON that matches the schema exactly, with no other keys.
- events: things that happen or states that change, each with a short key, a label, the modality the text
  gives it (fact, memory, dream, rumor, metaphor or hypothesis), the names of participants as the text writes
  them, and one or more exact quotes from a passage (its ref) as evidence. A recalled scene is "memory".
- anchors: ages, dates or relative times the quote attaches to an event (kind age, date or relative).
- relations: temporal order only when the quoted text states it: before, after, during, overlaps, or unknown
  when the text says the order is not known. Never infer an order from where a passage appears in the book.
The data item "{KNOWN_REF}" lists events from earlier chapters; refer to one by its key (they start with
"k:") instead of declaring it again. Never quote that item as evidence."""


class Evidence(StructuredOutput):
    ref: Ref
    quote: Quote


class ExtractedEvent(StructuredOutput):
    key: Key
    label: Label
    modality: Modality
    participants: list[Label] = Field(default=[], max_length=16)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class ExtractedAnchor(StructuredOutput):
    event: EventKey
    kind: Literal["age", "date", "relative"]
    value: Annotated[str, Field(min_length=1, max_length=64)]
    ref: Ref
    quote: Quote


class ExtractedTemporal(StructuredOutput):
    source: EventKey
    relation: TemporalRelation
    target: EventKey
    ref: Ref
    quote: Quote


class EventExtraction(StructuredOutput):
    schema_version = "events-schema-v1"
    events: list[ExtractedEvent] = Field(max_length=200)
    anchors: list[ExtractedAnchor] = Field(default=[], max_length=200)
    relations: list[ExtractedTemporal] = Field(default=[], max_length=400)


def event_request(sources: list[SourceItem], known: str, limits: Limits) -> ProviderRequest:
    items = [*sources, SourceItem(ref=KNOWN_REF, text=known)] if known else sources
    return ProviderRequest(role="extraction", purpose="narrative.events", prompt_version=PROMPT_VERSION,
                           instructions=INSTRUCTIONS, sources=tuple(items), limits=limits)
