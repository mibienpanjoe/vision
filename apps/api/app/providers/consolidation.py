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

PROMPT_VERSION = "consolidate-v8"
REQUEST_REF = "request"

INSTRUCTIONS = f"""Consolidate the selected book passages into source-grounded visual facts at the requested scene.
The "{REQUEST_REF}" item contains the reader's words, subject, moment, scene and a cutoff-safe entity registry.
It is derived context, never evidence. Use registry refs for subjects, participants and identity endpoints;
unique visible aliases may resolve, shared titles never do. Never invent an entity ref.
Return the schema exactly:
- events: minimal relevant happenings or state changes, each with a key, label, modality, participants and
  exact ref+quote evidence. Recalled events are memory; distinguish fact, dream, rumor, metaphor and hypothesis.
- anchors: quoted ages, dates or relative times attached to events.
- relations: quoted before/after/during/overlaps/unknown order. Source order alone is not story-time order.
- facts: atomic subject, short snake_case attribute, value in the text's words, exact evidence. kind is
  identity/acquired/interval/scene; scene facts require event keys. Explicit support needs a quote stating
  the entire claim; inferred support requires an assumption. Mark a denial/removal negated. Keep modality
  and any non-narrator perspective. Link every event where the quotes establish the fact; leave events empty
  only when the text presents it as timeless. Never link a trait to every later event merely by persistence.
- identity_links: quoted same-person/thing statements, explicit only when stated, otherwise inferred.
- requested_event: key of the event established by passages as the requested scene, otherwise null.
  Read the full request AND moment AND scene together; after the war alone is not necessarily dinner.
Important distinctions:
- roof_material=slate does not establish roof_condition. "Fire destroyed the house's slate roof" supports
  roof_condition=destroyed on the explicitly named house at destruction. Later restoration never applies
  earlier. Explicitly owned components may be owner attributes; a nearby room is not automatically the house.
- Removed armor is negated at removal, not affirmed clothing. A new garment applies only where stated;
  never assume clothing persists into another scene.
- An acquired scar belongs to injury. Reconstruction handles later carry-forward as inference. If the text
  says the scar is visible at dinner, quote that direct statement and link the fact to dinner.
- An object's material can be established in the person's age-ten scene; the object itself need not be ten.
Extract requested conditions as well as materials. Attribute only to the stated entity. Quotes come only
from source passages, never these examples. Omit unsupported details and do not invent a missing moment."""


class Evidence(StructuredOutput):
    ref: Ref
    quote: Quote


class ConsolidatedFact(StructuredOutput):
    subject: Label
    attribute: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$", description="Component and property, e.g. roof_condition or roof_material; keep them distinct.")]
    value: Annotated[str, Field(min_length=1, max_length=256)]
    kind: FactKind
    support: Literal["explicit", "inferred"]
    modality: Literal["fact", "memory", "dream", "rumor", "metaphor", "hypothesis"]
    polarity: Literal["affirmed", "negated"] = "affirmed"
    perspective: Annotated[str, Field(max_length=256)] | None = None
    assumption: Annotated[str, Field(max_length=256)] | None = None
    events: list[Key] = Field(default=[], max_length=8, description="Only events where quoted evidence establishes this fact, not all later events.")
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class IdentityLink(StructuredOutput):
    subject: Label
    object: Label
    support: Literal["explicit", "inferred"]
    ref: Ref
    quote: Quote


class Consolidation(StructuredOutput):
    schema_version = "consolidation-schema-v3"
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
