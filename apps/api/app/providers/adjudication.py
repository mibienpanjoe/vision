"""Source-bound adjudication role: does each quoted span state this exact claim?

A verdict counts only with a quote copied from that claim's own evidence; a
verdict without one is ignored, so a bare confidence answer can neither approve
nor reject anything.
"""

from typing import Annotated, Literal

from app.providers.contracts import (
    Limits,
    ProviderRequest,
    SourceItem,
    StructuredOutput,
)
from app.providers.extraction import Quote
from pydantic import Field

PROMPT_VERSION = "adjudicate-v4"

INSTRUCTIONS = """You check claims against the exact book quotes given with each claim.
Each source item is one claim: its subject, attribute, value, the complete reader request, story moment,
scene, resolved event with grounding quotes, the claim quotes, and the passages
around them as context, so a pronoun in a quote can be traced to the person it names. Decide only from the
quotes, read in that context.
Use the full request, scene and resolved event together: "after the war" alone does not identify dinner
or spring. The request and labels are not evidence; event quotes only anchor the moment.
The first claim also carries related_passages selected within the reader boundary; use them for changes,
removals and contradictions affecting ANY claim. related_complete=false means some context could not fit.
For every claim return exactly one verdict:
- entailed: a quote states that this subject has this value for this attribute at this moment;
- not_entailed: the quotes do not state it (a rumor, dream, metaphor, question, denial or another subject's
  trait does not state it);
- contradicted: a quote states something incompatible.
Always copy the exact deciding words into "quote". Entailed needs the claim's own quotes; rejection may
quote its own evidence or a related passage. A valid quote alone does not prove the whole claim. Return JSON that matches the schema exactly."""

Verdict = Literal["entailed", "not_entailed", "contradicted"]


class ClaimVerdict(StructuredOutput):
    claim: Annotated[str, Field(pattern=r"^c[0-9]{1,3}$")]
    verdict: Verdict
    quote: Quote


class Adjudication(StructuredOutput):
    schema_version = "adjudication-schema-v1"
    verdicts: list[ClaimVerdict] = Field(max_length=64)


def adjudication_request(claims: list[SourceItem], limits: Limits) -> ProviderRequest:
    return ProviderRequest(role="reasoning", purpose="verification.adjudicate", prompt_version=PROMPT_VERSION,
                           instructions=INSTRUCTIONS, sources=tuple(claims), limits=limits)
