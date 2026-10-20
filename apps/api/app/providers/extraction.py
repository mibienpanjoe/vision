"""Entity-extraction role: request composition and the structured output contract.

The model quotes source text instead of giving offsets; the narrative service
grounds each quote in its passage and rejects anything it cannot find.
"""

from typing import Annotated, Literal

from app.providers.contracts import (
    Limits,
    ProviderRequest,
    SourceItem,
    StructuredOutput,
)
from pydantic import Field

PROMPT_VERSION = "entities-v2"
KNOWN_REF = "known-entities"
Kind = Literal["character", "place", "object", "organization"]
RelationType = Literal["same_as", "carries", "located_at", "member_of", "family_of", "associated_with"]
Key = Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,32}$")]
# A key declared in this response, or `k:n` for an entity listed from earlier chapters.
EntityRef = Annotated[str, Field(pattern=r"^(k:)?[a-z0-9_-]{1,32}$")]
Quote = Annotated[str, Field(min_length=1, max_length=400)]
Ref = Annotated[str, Field(min_length=1, max_length=128)]
Label = Annotated[str, Field(min_length=1, max_length=256)]

INSTRUCTIONS = f"""You extract narrative entities from numbered book passages.
Return JSON that matches the schema exactly, with no other keys.
- entities: every character, place, object or organization named or described; give each a short key and the
  name the text uses for it. A title such as "the captain" is not a name.
- mentions: each occurrence, as the exact quote copied from one passage (its ref). Set "entity" only when the
  passage itself makes the identity clear; when a phrase could refer to more than one entity, leave "entity"
  null and list every plausible key in "candidates".
- aliases: other names or titles for an entity, with the exact quote that supports them; status "supported"
  when the text states the mapping, otherwise "candidate".
- relations: only relations the quoted text states; "same_as" only when the text explicitly says two
  entities are the same.
The data item "{KNOWN_REF}" lists entities from earlier chapters; when a passage refers to one of them, use
its key (they start with "k:") instead of declaring it again. Never quote that item.
Never merge entities because they share a title, and never add facts the passages do not state."""


class ExtractedEntity(StructuredOutput):
    key: Key
    kind: Kind
    label: Label


class ExtractedMention(StructuredOutput):
    ref: Ref
    quote: Quote
    entity: EntityRef | None = None
    candidates: list[EntityRef] = Field(default=[], max_length=8)


class ExtractedAlias(StructuredOutput):
    entity: EntityRef
    label: Label
    status: Literal["supported", "candidate"]
    ref: Ref
    quote: Quote


class ExtractedRelation(StructuredOutput):
    subject: EntityRef
    relation: RelationType
    object: EntityRef
    ref: Ref
    quote: Quote


class EntityExtraction(StructuredOutput):
    schema_version = "entities-schema-v2"
    entities: list[ExtractedEntity] = Field(max_length=200)
    mentions: list[ExtractedMention] = Field(max_length=1_000)
    aliases: list[ExtractedAlias] = Field(default=[], max_length=200)
    relations: list[ExtractedRelation] = Field(default=[], max_length=200)


def entity_request(sources: list[SourceItem], known: str, limits: Limits) -> ProviderRequest:
    items = [*sources, SourceItem(ref=KNOWN_REF, text=known)] if known else sources
    return ProviderRequest(role="extraction", purpose="narrative.entities", prompt_version=PROMPT_VERSION,
                           instructions=INSTRUCTIONS, sources=tuple(items), limits=limits)
