# Narrative identity, chronology, and appearance contract

**Status:** baseline semantics; carry-forward adjudication remains OPEN-04.
**Data owner:** [canonical model](../data/canonical-model.md).

## Identity and attribution

An entity is a character, place, object, or other narrative identity, scoped to
a work. A mention is a source occurrence, not an entity by itself. A nickname
or title is an alias candidate until its mapping is supported. Store unresolved
alternatives rather than merging every occurrence of “the captain.”

Resolve pronouns using sufficient neighboring context. “His armor,” dialogue
about another person, and negation must retain their actual owner and meaning.
A fact about a sword does not become a trait of its wielder unless an explicit
relationship makes that distinction clear in the output.

## Two independent axes of time

Source position identifies where information is revealed. Story time identifies
when an event or property applies. Keep both even when one is unknown.

Event relations may form a partial order: before, after, during, overlaps, or
unknown. Conflicting relations must be surfaced rather than forced into an
ordered list. A dream or metaphor is not a chronology update. “Chapter 14” may
name a source boundary; “at age ten” names a story-time constraint.

## Appearance claims

| Kind | Applicability |
|---|---|
| Identity trait | Applicable where supported; not automatically valid at every age |
| Acquired change | Begins with an evidenced event; persistence requires a justified rule |
| Interval state | Valid within an established interval; uncertain endpoints remain uncertain |
| Scene-specific attribute | Clothing, props, posture, lighting, or situation in that scene |
| Inferred detail | Reasoned from admissible evidence with assumptions recorded |
| Creative completion | Added for rendering; never attributed to the author |

A missing end event means “no end established,” not “permanent.” The source
example permits a later scar where persistence is justified; how to classify
an absence-of-contradiction inference must be settled before implementation.
Until then, do not promote this inference into explicit canonical evidence.

## Reconstruction operation

Input scope includes work, entity candidates, requested event/age/interval,
scene context, source cutoff, creative mode, and processing generation.

The operation checks evidence eligibility, resolves identity and time, evaluates
applicable claims, applies justified changes, overlays scene details, and returns
a state or a reason it cannot do so. Ordering that is unknown cannot support a
definite “before” or “after” claim. Contradictions are resolved only when context
or better evidence explains them; otherwise they remain disputed.

The detailed retrieval/reconstruction algorithm belongs to the
[retrieval strategy](../architecture/retrieval-strategy.md), not a separate pipeline here.

## Spoiler eligibility

Apply the reading boundary to passages and every derived decision: identity
merges, alias labels, event names, relationship resolutions, context options,
facts, contradictions, and cached states. Later source material describing an
earlier event remains out of scope for a reader who has not reached it.

For a proposed first implementation, use dependency closure: all inputs needed
to justify a displayed assertion must be eligible. A whole-book entity index
filtered only by the final displayed citation is insufficient. When provenance
cannot prove a derived record eligible, recompute from in-scope inputs or omit
the assertion. Never use a whole-book state as a cutoff-specific cache hit.

## Discriminated outcomes

Conceptual outcomes are `resolved`, `needs_context`, `insufficient_evidence`, and
`failed`. A resolved state may contain unknown or disputed attributes; their
presence must not imply certainty. Exact serialized names are part of the API
draft. Context choices themselves must pass spoiler and ownership checks.
