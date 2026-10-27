# Visual specification and grounding contract

**Status:** executable schema `vision-spec-1.0` (`app/schemas/visualization.py`,
T31) behind `POST /v1/works/{work_id}/visualizations/compose`; see the
[API contract](../api/api-contract.md#visualization-compose--t31). Resolved results
are stored and cached (T32); the browser composes, inspects and exports their
specifications (T37). There is no image-provider integration.

## Inputs and outcomes

A request specifies the work, natural-language query and/or entity, requested
story moment, scene context, reading boundary, creative mode, style preferences,
and any locked canonical facts. Broad queries can return context choices.
Insufficient evidence returns a visible limitation rather than invented canon.

After reconstruction and verification, compose a provider-independent visual
specification. Provider prompts are adapters over that specification; they must
not silently introduce incompatible appearance details.

## Output fields

| Group | Required meaning |
|---|---|
| Schema and lineage | Schema version, document/index generation, relevant processing/model/prompt versions |
| Subject | Resolved entity IDs and types, or explicitly unresolved candidates |
| Scope | Requested and resolved time/context, reading boundary, creative mode |
| Canonical profile | Verified explicit attributes applicable here, each with attribute-level evidence |
| Inferred profile | Reasoned details, supporting evidence, assumptions, and uncertainty |
| World context | Source-backed setting/environment and separately labeled inferred or creative completion |
| Unknowns and conflicts | Missing traits, incompatible evidence, unresolved chronology, and their consequences |
| Creative additions | Artistic defaults and interpolations, never source quotations |
| Generation | Style, composition, aspect ratio and provider-neutral prompt intent; provider-specific fields are optional |
| Evidence | Resolvable source revision, passage and span references, and their support roles |

Creative additions may have no textual evidence; canonical claims may not.
World-setting claims follow the same grounding rules as character traits.
Never let an uncited environment or final free-text prompt bypass verification.

## Validation gates

1. Validate the typed structure and supported schema version.
2. Check authorization, source revision, index compatibility, and every reference.
3. Check reading eligibility of each claim and its derivation dependencies.
4. Verify entity ownership, textual entailment, modality, negation, and attribution.
5. Verify temporal/context applicability and incompatible claims.
6. Separate explicit, inferred, creative, unknown, and disputed fields.
7. Check the final prompt against the verified profile and locked canonical facts.

Schema validation alone cannot establish factual grounding. Model adjudication
is tied to admissible source spans; an unqualified confidence statement is not
a passed gate. Failed canonical claims are removed or reclassified explicitly,
and relevant uncertainty remains visible.

### Attribute and prompt gates — T30

`services/verification/claims.py` re-checks every fact behind a reconstructed
trait against storage before composition. Each check removes the fact with a
stable reason; a trait with no surviving fact is removed:

| Check | Reason |
|---|---|
| Fact belongs to the requested subject (or its explicitly linked identity) | `wrong_owner` |
| Has evidence | `no_evidence` |
| Spans lie in the plan's document and parser revision and inside the passage | `span_mismatch` |
| Every span and every linked event's evidence is inside the reading boundary | `beyond_boundary` |
| An evidence passage names the subject or holds a mention resolved to it | `unattributed` |
| Canonical: explicit, affirmed, fact or memory | `not_canonical` |
| Canonical: value asserted in its quotes, outside negation, removal, question or hedge | `unsupported_value` |
| Canonical: tied to the requested event; inference: at least before it | `not_at_this_moment` |

Kept traits carry their `SourceSpan` evidence per fact. Optional adjudication
(`adjudicate-v3`, role `reasoning`) sends each surviving canonical claim with the
full reader request, moment, scene, resolved event and its cutoff-safe grounding quotes, alongside its
quotes and their passages as context. A verdict counts only when its quote is
copied from that claim's own evidence. `entailed` marks the trait and nothing
more; `not_entailed` or `contradicted` removes the fact. An unquoted verdict
counts for nothing, and a provider failure leaves the deterministic result
with adjudication `unavailable`. Adjudication runs on survivors only, so it can
never approve or promote a claim. A live Groq sample on the synthetic dinner
(985 input and 211 output tokens, 0.9 s) entailed both the linen shirt and the
visible scar. Without passage context it had rejected the scar because the
quote says "his", which led to the context field.

`prompt_problems` checks a final prompt. It fails when an excluded or removed
value appears and no kept value contains it, when a disputed trait's value
appears as settled, when a lock is not a kept canonical value or is missing
from the prompt, when a creative addition is quoted, or when the text reads as
an instruction ("ignore", "reveal", "system prompt" and similar). An empty
list passes.

## Refinement and history

Changing style does not change canon. Changing the subject, moment, reading
boundary, or locked facts requires revalidation and a correctly scoped derived
state. Preserve output revisions and processing lineage; exact revision tokens
follow the [API conventions](../api/api-contract.md#selected-first-slice-wire-conventions);
The [presentation refinement API](../api/api-contract.md#presentation-refinements--t38)
implements conditional style/mode/lock changes. It retains every profile and
source span unchanged, gates the recomposed prompt, and refuses stale dependencies
until a fresh reconstruction. Creative additions never exempt excluded values
from the prompt gate.

An optional rendered image references its specification revision, provider/model,
settings, and outcome. The image can be aesthetically plausible and still fail
the textual contract; generated pixels never become evidence for new facts.
[Image rendering](../api/api-contract.md#image-rendering--t40) sends only the
gated `generation.prompt`; the selected model takes no negative prompt, so
excluded values are not enforced by the provider and must be checked in the
pixels. The composed prompt (`compose-v4`, part of the result cache key) states a
single scene, counts the other people present and omits an object already named
as a member's trait value, so image models neither merge people, split them into
panels nor redraw the object twice. The subject stands in the foreground and its
traits are separate sentences; a mark on a facial region (face, cheek, forehead,
brow, temple, chin, jaw, nose, neck) comes first, is asked to be in clear view and
turns the subject toward the viewer, because a parenthesised scar was never drawn.
A left or right mark on the subject also names the side of the image it falls on,
since a person facing the viewer shows their left on the image's right and image
models otherwise mirror it.

## Synthetic example policy

Examples using Arthur are fictional and illustrative. IDs such as `p-241` in
the source brief are not citations to a stored book. Executable examples will
be generated from synthetic fixture passages with resolvable spans when the
schema is implemented.
