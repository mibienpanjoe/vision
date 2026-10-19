# Visual specification and grounding contract

**Status:** baseline output semantics; executable JSON Schema not yet defined.
The overview example is abbreviated. This document does not freeze version 1.0
or claim a working image-provider integration.

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

## Refinement and history

Changing style does not change canon. Changing the subject, moment, reading
boundary, or locked facts requires revalidation and a correctly scoped derived
state. Preserve output revisions and processing lineage; exact revision tokens
and mutation endpoints remain OPEN-07.

An optional rendered image references its specification revision, provider/model,
settings, and outcome. The image can be aesthetically plausible and still fail
the textual contract; generated pixels never become evidence for new facts.

## Synthetic example policy

Examples using Arthur are fictional and illustrative. IDs such as `p-241` in
the source brief are not citations to a stored book. Executable examples will
be generated from synthetic fixture passages with resolvable spans when the
schema is implemented.
