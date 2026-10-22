# Product requirements and acceptance

**Status:** target product requirements; local application foundation implemented.
Full product acceptance remains pending.
**Sources:** [overview](project-overview.md),
[retrieval strategy](../architecture/retrieval-strategy.md).

These requirements describe the target product. They are not a list of delivered
features. Direct image rendering follows the structured-output milestone.
Physical schemas and API wire shapes remain drafts unless the register says otherwise.

## Product outcome

An authorized reader uploads a narrative work, selects or describes a subject
and moment, and receives an inspectable visual reconstruction with valid JSON.
Canonical detail is tied to actual evidence; uncertainty and creative completion
remain visible. The original text remains the source of truth.

## Requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| REQ-01 | Private library | Another owner cannot discover or read a work or any derived object through lists, IDs, jobs, caches, or assets. |
| REQ-02 | Source-preserving ingestion | PDF, EPUB, TXT, and Markdown adapters preserve originals and return versioned passages with inspectable anchors; unavailable chapter/page structure is reported. |
| REQ-03 | Durable background progress | The reader sees queued/running/terminal status, stage, safe failures, retry, and cancellation outcomes; accepting a job does not imply success. |
| REQ-04 | Stable evidence | An attribute resolves to an exact passage span from the document revision used; reprocessing does not silently retarget old citations. |
| REQ-05 | Entity resolution | Names, titles, nicknames, and pronouns resolve only when supported; two captains are not merged solely by title. |
| REQ-06 | Partial story chronology | A later flashback can describe an earlier state; unknown or contradictory ordering is retained explicitly. |
| REQ-07 | Scoped visual facts | Identity traits, acquired changes, interval properties, and scene clothing are distinguishable and reconstructible. |
| REQ-08 | Hybrid evidence retrieval | Entity-linked facts, lexical results, and semantic results contribute evidence; protected canonical facts survive low similarity ranks. |
| REQ-09 | Correct temporal reconstruction | A childhood result excludes a later injury; a later result applies only justified persistent changes. |
| REQ-10 | Situational accuracy | Battle and home appearances can differ in clothing and props without changing identity; removing armor is not interpreted as wearing it afterward. |
| REQ-11 | Spoiler boundary | Out-of-scope passages and derived conclusions cannot affect entities, context options, retrieval, caches, profiles, or exported specifications. |
| REQ-12 | Meaningful disambiguation | When distinct supported identities or appearances remain, return options or explicit uncertainty rather than a blended appearance. |
| REQ-13 | Attribute verification | Wrong-owner, unsupported, future-only, or out-of-cutoff claims are rejected as canonical even if the JSON structure is valid. |
| REQ-14 | Evidence and uncertainty UX | An attribute opens its exact supporting excerpt; inferred, creative, disputed, and unknown details are distinguishable. |
| REQ-15 | Two creative modes | Canon-first keeps only verified explicit claims canonical; interpretation mode labels additions and preserves locked canonical facts. |
| REQ-16 | Structured portable output | A typed, versioned specification contains subject, scope, profile, evidence, uncertainty, creative choices, and generation settings. |
| REQ-17 | Reproducible processing | Results record document, parser, extraction, embedding, retrieval, prompt, schema, and model versions/configurations as applicable. |
| REQ-18 | Safe reprocessing and caching | Rebuilding indexes or changing a reading boundary cannot reuse an incompatible state; dependent caches are invalidated or namespaced. |
| REQ-19 | Bounded operation | Uploads, extraction, retrieval context, model calls, and rendering have configurable limits and explicit exhaustion outcomes. |
| REQ-20 | Optional rendering | An image is generated only from a validated specification through an adapter; its provenance remains the specification, never new textual evidence. |
| REQ-21 | Replaceable model roles | Extraction, reasoning, embedding, reranking, and rendering integrations can be tested and replaced behind narrow contracts. |
| REQ-22 | Untrusted source handling | Document instructions cannot change tools, system behavior, credentials, or ownership scope. |

REQ-15 uses the conservative canonical-field interpretation of the brief. The
first-slice carry-forward rule is selected by [DEC-22](decision-register.md) and
owned by the [narrative contract](../narrative/narrative-contract.md).
A model confidence score alone cannot satisfy REQ-13.

## Product flow and outcomes

```text
Upload → inspect ingestion status → explore entities/contexts
  → choose moment and reading boundary → request reconstruction
  → resolve ambiguity if needed → inspect profile and excerpts → export JSON
  → optionally render and retain the resulting artifact
```

Insufficient evidence is a useful visible outcome, not a reason to fabricate a
complete canonical portrait. A context-selection response is not a completed
visualization. Parsing and provider failures must not display a successful result.

## Boundaries

The baseline excludes PageIndex, standalone graph/vector/search infrastructure,
and multi-agent orchestration. Public book sharing, voice interaction, authoring
tools, and licensed content acquisition are not defined product capabilities.
Agent-interface component libraries do not change those boundaries.

The [acceptance strategy](../testing/acceptance-strategy.md) maps these IDs to
executable scenarios and remaining verification limits. The [roadmap](implementation-roadmap.md) sets their
delivery sequence without removing foundational safety and provenance requirements.
