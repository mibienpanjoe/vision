"""Query-time consolidation role (DEC-38): events, visual facts and identity links in one call.

Only passages already selected inside the reader's boundary are sent. The model
quotes them; every quote is grounded again before anything is stored, and the
existing event and fact gates decide what survives.
"""

from typing import Annotated, Literal

from app.providers.contracts import (
    Limits,
    ProviderRequest,
    SourceItem,
    StructuredOutput,
)
from app.providers.events import ExtractedAnchor, ExtractedEvent, ExtractedTemporal
from app.providers.extraction import Key, Label, Quote, Ref
from app.providers.visual_facts import FactKind
from pydantic import Field

PROMPT_VERSION = "consolidate-v4"
REQUEST_REF = "request"

INSTRUCTIONS = f"""You consolidate what numbered book passages say about how one subject looks and, when the
request names participants or a scene, how those people, the objects they hold and the place look there.
The data item "{REQUEST_REF}" names the subject, the story moment and the scene the reader asked about;
it is derived data, never evidence. Return JSON that matches the schema exactly, with no other keys.
- events: things that happen or states that change and matter for appearance or the scene, each with a short
  key, a label, its modality (fact, memory, dream, rumor, metaphor or hypothesis), participants as the text
  names them and exact quotes (ref + quote) as evidence. A recalled scene is "memory".
- anchors: ages, dates or relative times the quote attaches to an event.
- relations: temporal order only when the quoted text states it (before, after, during, overlaps, unknown).
  Never infer an order from where a passage appears.
- facts: atomic visual facts, one subject, one attribute (short snake_case), one value in the text's words.
  kind: identity, acquired, interval or scene (scene facts name their event keys); support explicit when a
  quote states it, inferred with the assumption stated; polarity negated when the text denies or removes it;
  modality as the text presents it; perspective when someone other than the narrator describes it.
  events: the keys of every event at which the fact holds, as the quotes place it. A trait stated for one
  time (a child's hair, a coat worn that day, armor worn in a battle) is linked to that time's event; leave
  events empty only for a trait the text presents as timeless.
- identity_links: only when a quote says two names are the same person or thing; "explicit" when the quote
  states it, otherwise "inferred".
- requested_event: the key of your event that is the moment or scene the reader asked about, or null when the
  passages do not establish that moment. Never invent an event to fill it. Facts that hold at that moment list
  its key.
Attribute every fact only to the entity the text gives it to, and quote text exactly as written.
Never add details the passages do not support; leave out what they do not say."""


class Evidence(StructuredOutput):
    ref: Ref
    quote: Quote


class ConsolidatedFact(StructuredOutput):
    subject: Label
    attribute: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    value: Annotated[str, Field(min_length=1, max_length=256)]
    kind: FactKind
    support: Literal["explicit", "inferred"]
    modality: Literal["fact", "memory", "dream", "rumor", "metaphor", "hypothesis"]
    polarity: Literal["affirmed", "negated"] = "affirmed"
    perspective: Annotated[str, Field(max_length=256)] | None = None
    assumption: Annotated[str, Field(max_length=256)] | None = None
    events: list[Key] = Field(default=[], max_length=8)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class IdentityLink(StructuredOutput):
    subject: Label
    object: Label
    support: Literal["explicit", "inferred"]
    ref: Ref
    quote: Quote


class Consolidation(StructuredOutput):
    schema_version = "consolidation-schema-v2"
    events: list[ExtractedEvent] = Field(default=[], max_length=60)
    anchors: list[ExtractedAnchor] = Field(default=[], max_length=60)
    relations: list[ExtractedTemporal] = Field(default=[], max_length=120)
    facts: list[ConsolidatedFact] = Field(default=[], max_length=120)
    identity_links: list[IdentityLink] = Field(default=[], max_length=16)
    requested_event: Key | None = None


def consolidation_request(sources: list[SourceItem], request: str, limits: Limits) -> ProviderRequest:
    return ProviderRequest(role="reasoning", purpose="retrieval.consolidation", prompt_version=PROMPT_VERSION,
                           instructions=INSTRUCTIONS, sources=(*sources, SourceItem(ref=REQUEST_REF, text=request)),
                           limits=limits)
