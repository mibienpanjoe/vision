"""Visual-fact extraction role: atomic subject/attribute/value claims with scope and support.

Support is only explicit or inferred; creative completion is not a valid value,
so it cannot enter source canon through this contract.
"""

from typing import Annotated, Literal

from app.providers.contracts import (
    Limits,
    ProviderRequest,
    SourceItem,
    StructuredOutput,
)
from app.providers.events import Evidence, Modality
from app.providers.extraction import Label
from pydantic import Field

PROMPT_VERSION = "facts-v1"
KNOWN_REF = "known-events"
FactKind = Literal["identity", "acquired", "interval", "scene"]

INSTRUCTIONS = f"""You extract atomic visual facts from numbered book passages: one subject, one attribute,
one value each (hair, eyes, left_cheek, attire, held_object, material, roof, lighting, body, ...).
Return JSON that matches the schema exactly, with no other keys.
- subject: the entity's name exactly as the text names it; attribute: short snake_case; value: the text's words.
- kind: identity (stable trait), acquired (a change from an event), interval (true for a period), scene
  (clothing, props, posture, lighting in one scene). Scene facts must name their event.
- support: explicit when a quote states it; inferred when reasoned from quotes, with the assumption stated.
- modality: fact, memory, dream, rumor, metaphor or hypothesis, as the text presents it.
- polarity: negated when the text says the subject does not have it (e.g. armor removed, "not Arthur").
- perspective: who describes it, if not the narrator.
- events: keys from the "{KNOWN_REF}" data item the fact applies to.
Attribute a fact only to the entity the text gives it to. Never add details the passages do not support."""


class ExtractedFact(StructuredOutput):
    subject: Label
    attribute: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    value: Annotated[str, Field(min_length=1, max_length=256)]
    kind: FactKind
    support: Literal["explicit", "inferred"]
    modality: Modality
    polarity: Literal["affirmed", "negated"] = "affirmed"
    perspective: Annotated[str, Field(max_length=256)] | None = None
    assumption: Annotated[str, Field(max_length=256)] | None = None
    events: list[Annotated[str, Field(pattern=r"^e:[0-9]{1,4}$")]] = Field(default=[], max_length=8)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class FactExtraction(StructuredOutput):
    schema_version = "facts-schema-v1"
    facts: list[ExtractedFact] = Field(max_length=400)


def fact_request(sources: list[SourceItem], known: str, limits: Limits) -> ProviderRequest:
    return ProviderRequest(role="extraction", purpose="narrative.visual_facts", prompt_version=PROMPT_VERSION,
                           instructions=INSTRUCTIONS, sources=(*sources, SourceItem(ref=KNOWN_REF, text=known)),
                           limits=limits)
