# Narrative identity, chronology, and appearance contract

**Status:** first-slice temporal and cutoff rules selected by T02 (DEC-22).
DEC-37 ([ADR-0003](../adr/0003-local-ingestion-minimal-disclosure.md)) moves
private-book extraction to local models and consolidation to query time; the
proposed contract for that change is
[PROP-08](#local-ingestion-and-query-time-consolidation--prop-08). The T18–T20
LLM derivations below remain the synthetic-fixture path and evaluation baseline.
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

### Entity derivation — T18

`services/narrative/entities.py` derives entities for one source generation
as a versioned `derivations` row (stage `entities`, processing version =
prompt/schema/provider/model). A changed prompt, schema or model creates a new
derivation; earlier derivations and their rows are never rewritten. Passages are
sent in chapter-aligned batches within the provider limits.

The model returns quotes, not offsets. Each mention, alias and relation is kept
only when its quote is found verbatim in the referenced passage (alias labels
must also appear in the quote) and its entity keys were declared; otherwise it is
counted by reason in `derivations.rejections` without storing text. Entities
without a grounded mention are dropped. Later batches receive the entities
declared by earlier batches as a separate derived data item and reuse them by
`k:n` key; otherwise identities from different batches unify only on identical
kind and case-folded label. Titles never merge identities.
A mention with no supported identity keeps `entity_id` null and lists its
candidates; an identity link such as Wren = Arthur is a `same_as` relation
carrying its own chapter-five span, so T21 can apply it only within scope.

Publication is all-or-nothing under the derivation row lock and an attempt
counter: a failed, cancelled or superseded attempt stores only its model runs.
Each batch may make up to three calls when the outcome is invalid output,
unavailable or timeout (a routed gateway can pick a weak or overloaded model);
every call is recorded. A failed derivation can be retried; a succeeded one is
returned unchanged.

## Two independent axes of time

Source position identifies where information is revealed. Story time identifies
when an event or property applies. Keep both even when one is unknown.

Event relations may form a partial order: before, after, during, overlaps, or
unknown. Conflicting relations must be surfaced rather than forced into an
ordered list. A dream or metaphor is not a chronology update. “Chapter 14” may
name a source boundary; “at age ten” names a story-time constraint.

### Event derivation and partial chronology — T19

`services/narrative/events.py` derives events from one succeeded entity
derivation of the same generation, recorded as the derivation's input; a new
entity derivation therefore yields a new event derivation. Each event keeps its
modality (fact, memory, dream, rumor, metaphor, hypothesis), at least one grounded
evidence span, temporal anchors (age, date, relative) with their spans, and
participants matched to entities by exact label only. Later chapters receive the
earlier chapters' event list as a separate derived data item and refer to those
events by `k:n` keys; quoting that item as evidence is rejected.

Relations are stored exactly as stated (before, after, during, overlaps,
unknown). `services/narrative/chronology.py` computes a partial order over fact
and memory events only: transitive `before`, `after` normalised, and an event
`during` another inheriting its container's order. Events on a stated cycle
return `inconsistent` and are not used as intermediates, and an overlap that
contradicts a definite order is `inconsistent`. Pairs without stated support
remain `unknown`; source position (evidence passage order) is never used as
story order, so a chapter-five memory of childhood orders before the war while
being revealed after it.

## Appearance claims

| Kind | Applicability |
|---|---|
| Identity trait | Applicable where supported; not automatically valid at every age |
| Acquired change | Begins with an evidenced event; persistence requires a justified rule |
| Interval state | Valid within an established interval; uncertain endpoints remain uncertain |
| Scene-specific attribute | Clothing, props, posture, lighting, or situation in that scene |
| Inferred detail | Reasoned from admissible evidence with assumptions recorded |
| Creative completion | Added for rendering; never attributed to the author |

A missing end event means “no end established,” not “permanent.” Canonical
carry-forward requires eligible explicit evidence of the trait at the requested
moment or an explicit persistence interval covering it. A scar acquired in war
and explicitly still present at home is canonical at home; acquisition alone
can support only a labeled inference later. Unknown ordering or a later healing
contradiction blocks definite applicability. No wartime scar applies to childhood.
Scene clothing does not persist after an explicit removal; missing replacement
clothing remains unknown. This conservative rule resolves OPEN-04 for the first
slice; inference never becomes explicit solely through confidence or repetition.

### Visual fact derivation — T20

`services/narrative/visual_facts.py` derives atomic subject/attribute/value
facts from one succeeded event derivation (recorded as input). Each fact keeps
kind (identity, acquired, interval, scene), support (explicit or inferred; the
extraction schema has no creative value), modality, polarity (affirmed or
negated), optional perspective, an assumption for inferred facts, grounded
evidence spans and linked events. Batches only see events revealed up to their
chapter.

Deterministic gates run before storage: known subject; grounded quote; subject
named or resolved as a mention in an evidence passage; no explicit owner
negation such as "not Arthur"; inferred facts state their assumption; scene
facts name an event; and affirmed explicit facts need a value word asserted
outside a question and without a preceding negation (a negated name such as
"not Arthur" does not count). These are lexical guards, not entailment checks;
rejected facts are counted by reason. A fact is canonical only when explicit,
affirmed and presented as fact or memory.

`services/reconstruction/conflicts.py` records unresolved `fact_conflicts` for
canonical facts on the same subject and attribute with different values at a
shared event (or two unscoped identity traits), and summarises a subject at an
event as known, disputed (all values) or unknown, never an average.

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

For the first implementation, use dependency closure: all inputs needed
to justify a displayed assertion must be eligible. A whole-book entity index
filtered only by the final displayed citation is insufficient. When provenance
cannot prove a derived record eligible, recompute from in-scope inputs or omit
the assertion. Never use a whole-book state as a cutoff-specific cache hit.

### Reading-boundary implementation — T21

`services/narrative/eligibility.py` builds the visible narrative for one
generation and cutoff chapter (or the whole book). Passages qualify by chapter
ordinal. A mention is visible when its passage is; an entity when it has a
visible mention (resolved or as a candidate), with candidates restricted to
visible entities. The displayed label must be used by a visible mention,
otherwise the earliest visible mention text is shown, so a label chosen from a
later chapter cannot leak. Aliases and entity relations need a visible span and
visible endpoints, so a `same_as` link revealed later stays hidden and both
identities remain separate. Events need all evidence visible; participants,
anchors and relations are filtered the same way. Facts need all evidence, the
subject and every linked event visible; conflicts need both facts. Rows without
provenance do not exist by construction, so nothing is shown on trust.

## Local ingestion and query-time consolidation — PROP-08

Proposed contract for DEC-37. Identity, time, appearance and eligibility rules
above are unchanged; what changes is which component produces each record and
when.

**Ingestion stages (local, no network).** Each is a versioned derivation of the
source generation whose processing version names the model repository
revisions, precision, runtime versions and rule version.

| Stage | Input | Output |
|---|---|---|
| `entities` (local) | Passages | Entities, mentions, candidates, aliases, `same_as` relations |
| `appearance` | Passages, entity derivation | Appearance-candidate spans with their pattern and in-sentence mentions |
| `index` | Passages | Full-text and EmbeddingGemma vectors per passage (owned by the retrieval stage) |

Local entities follow the T18 storage contract with these rules:

- Mentions come from model offsets, and each is checked against the passage text
  before storage; a mismatch is a counted rejection.
- Identity rules are deterministic and versioned: one identity per proper name
  whatever its label; a full name folds into a surname that occurs alone; a lone
  first name folds into the single full name it starts; a title or role noun
  alone ("the captain", "the lawyer") stays a mention with candidates; a stop-list
  drops pronouns and function words tagged as names.
- Coreference runs per chapter (windows of whole passages above 40,000
  characters). A pronoun or descriptive mention resolves only when its cluster
  links exactly one identity; otherwise it keeps candidates.
- A `same_as` relation is created only when one chapter's coreference cluster
  links two proper-name identities, and it carries the span of the linking
  mention, so a reveal in chapter five stays invisible at a chapter-two cutoff.

Appearance candidates are pointers, not facts: a sentence span, the matched
pattern and the mentions it contains. They rank evidence for retrieval and
never become visual facts without consolidation. A generation is narrative-ready
when `entities` and `appearance` succeed.

**Consolidation (query time).** Events and visual facts are derived per
question as a `consolidation` derivation. Its input is the entity derivation
plus a scope: cutoff chapter, subject entity, requested time or context, and
the digest of the selected passage set. Only eligible passages selected by
local retrieval (target about 20 passages, about 5,000 tokens) are sent through
the provider envelope, in one call returning events and facts under a combined
strict schema to fit the provider's per-minute token budget.

The response goes through the existing pipeline unchanged: verbatim quote
grounding, event modality, partial chronology, the visual-fact gates,
canonical rules and conflict recording. Because every input is within the
cutoff, the dependency closure holds by construction; T21 eligibility is still
applied on read. The same scope and passage digest reuse a succeeded
consolidation instead of calling the provider again. A provider failure records
the run and returns a failed outcome with its code; it never falls back to
whole-book or unverified output.

Browse shows local entities, mentions and aliases at any cutoff, and events and
facts only from consolidations visible at that cutoff.

## Discriminated outcomes

Conceptual outcomes are `resolved`, `needs_context`, `insufficient_evidence`, and
`failed`. A resolved state may contain unknown or disputed attributes; their
presence must not imply certainty. Exact serialized names are part of the API
contract. Context choices themselves must pass spoiler and ownership checks.

## First corpus language

The first acceptance corpus and lexical configuration are English (`en`,
PostgreSQL `english`). Accented names, emoji and decomposed combining marks
exercise exact text preservation; they do not establish French or multilingual
linguistic support. Other language configurations and quality claims remain open.
A chapter-five childhood flashback is story-early but unavailable at a chapter-two
reading boundary. An alias resolved in chapter five cannot label an earlier
entity using that later dependency; retain admissible ambiguity instead.
