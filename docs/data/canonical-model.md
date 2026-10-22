# Canonical narrative data model

**Status:** conceptual baseline from overview §7; T10 implements works,
immutable original documents and queued ingestion jobs. Derived narrative
schemas remain planned.
This page owns object meaning, provenance, and relationship constraints.

## Source and derived layers

```text
Work → Document revision → Chapters → Scenes (optional) → Passages → Exact spans
                              ↓ extraction run / index generation
                     Mentions → Entities and aliases
                     Events → Temporal anchors and relations
                     Visual facts → Evidence and conflicts
                              ↓ scoped reconstruction
                     Appearance state → Visualization revision → Assets
```

A work is the reader's logical narrative. A document is an uploaded source
revision; translations or editions cannot be silently combined as one evidence
universe. Parser output and indexes are derived layers tied to that revision.
Physical IDs are opaque; their final storage type is an implementation choice.

## Object dictionary

| Object / intended table | Meaning and minimum relations |
|---|---|
| `works` | Private logical work; authorized owner, metadata, document references |
| `documents` | Original source revision; work, content fingerprint, format, storage reference |
| `chapters` | Source-order section; document, ordinal, title, anchors, structure quality |
| `scenes` | Optional scene grouping; source range, participants/context, boundary uncertainty |
| `passages` | Immutable parsed text; document/parser revision, chapter/scene where known, source anchors, neighboring passages |
| `derivations` | T18: one versioned derivation stage of a source generation; processing version, status, attempt, rejection counts. DEC-38 adds local `appearance` and query-scoped `consolidation` stages, the latter keyed also by cutoff, subject, requested scope and selected-passage digest |
| `entities` | Identity within a work; kind, preferred label, resolution status; T18 scopes each row to a derivation |
| `entity_aliases` | Candidate or supported names/titles; entity, scope, provenance, ambiguity |
| `entity_mentions` | Exact source occurrence; span, candidate entities (`mention_candidates`), resolved identity if justified, model run |
| `entity_relations` | Source-supported relationship between identities; type, temporal scope, evidence |
| `events` | Narrative event; label, participants, place, source evidence, temporal status; T19 stores modality, `event_evidence` spans and `event_participants` per derivation |
| `event_relations` | Before/after/during/overlap/unknown/inconsistent relation; linked events and support |
| `temporal_anchors` | Date, age, relative event, or uncertain interval; preserve granularity and evidence |
| `appearance_candidates` | DEC-38: local pointer to a likely description span; passage, span, cue words; `appearance_subjects` lists entities resolved inside it; ranks evidence, never a fact |
| `visual_facts` | Atomic claim about an entity; value, scope, temporal/context conditions, support/modality/status; T20 adds kind, polarity, perspective, assumption and `fact_events` |
| `fact_evidence` | Fact-to-source-span support with explicit or inferential role |
| `fact_conflicts` | Conflicting claims, compatible context distinctions, and unresolved resolution evidence |
| `appearance_states` | Derived scoped reconstruction; input generation, subject/time/context/cutoff/mode, dependencies |
| `visualizations` | Query and resulting specification revision; owner scope, state, versions, uncertainty |
| `visualization_evidence` | Output-attribute links to claims and exact spans used for the decision |
| `assets` | Original/derived files or rendered artifacts; storage reference, media type, originating document or visualization |
| `render_jobs` | Owned reservation of one immutable specification revision/hash and provider/model identity, request replay, revision/cancellation receipt, dispatch, claim and terminal outcome with safe error code, settings (size, quality or route, prompt digest), duration, provider-reported token usage and private output reference/digest/media type/size (DEC-51) |
| `ingestion_jobs` | Durable work attempts; document revision, stage, progress, terminal result, cancellation/retry lineage |
| `model_runs` | Provider/model role, processing configuration, inputs by safe reference, usage and outcome; T17 stores owner, optional generation, provider/model/version, prompt and schema versions, limits, input refs and SHA-256 digest, outcome/error code, token usage and duration, never source text, responses or credentials |

These names describe logical ownership, not final migrations. Owner identity,
access sessions, index-generation metadata, and revision representations must be
added explicitly when their open design choices are resolved.

## Provenance envelope

Every derived claim must be traceable through:

| Field | Rule |
|---|---|
| `work_id` / `document_id` | Same authorized source universe as every referenced object |
| `source_revision` | Immutable document/parser text revision used for the claim |
| `passage_id` + span | Existing text range; offset convention is defined in the ingestion proposal |
| `extraction_run` / `processing_version` | Identifies the derivation, not just the current model name |
| `support_type` | Explicit, inferred, or creative; creative content is not source canon |
| `perspective` / `modality` | Who describes it and whether it is fact, memory, dream, rumor, hypothesis, or metaphor |
| `temporal_constraints` | Applicable event(s), interval, or unknown ordering |
| `context_constraints` | Scene/place/situation conditions, including known exclusions |
| `dependencies` | Source and derived inputs needed to reach the conclusion; used for spoiler eligibility |

Unknown values remain unknown, rather than empty strings or guessed defaults.
No numeric certainty scale is defined yet. An LLM's certainty never overrides
source verification.

## Storage constraints

Use relational keys for identity, ownership, source links, events, and lineage;
JSONB may hold flexible visual values and specifications. All cross-references
must remain within the same work/revision unless an explicit future feature
defines cross-edition behavior.

Keep passage revisions and cited spans addressable after reprocessing, subject
to the future retention/deletion policy. Derived records can be superseded or
invalidated without rewriting old evidence. Cache keys must include processing
generation and request scope; cache hits are still subject to authorization.

An appearance state is computed, not a permanent universal portrait. It must
not erase the source claims or flatten distinct contexts into one entity row.
