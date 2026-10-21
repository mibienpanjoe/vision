# ADR-0003 — Local ingestion and minimal-disclosure query-time consolidation

**Status:** accepted (DEC-37), implementation pending.
**Recorded:** 2026-10-21; accepted by the maintainer 2026-10-21.
**Source:** [local-first processing research](../research/local-first-processing.md)
and its evaluation spike (section 10); DEC-36.

## Context

T18–T22 extract entities, events and visual facts with an LLM at ingestion, so
the whole private book reaches a model provider at least three times. The
FreeLLM gateway (DEC-24) routes each call to a different upstream whose data
handling Vision cannot control, `auto` routing is nondeterministic, and no free
tier has the capacity for whole-book extraction (Groq's free plan allows 8,000
tokens per minute on `gpt-oss-120b`). Provider data handling was not part of
the original architecture.

The spike measured local components on the synthetic corpus and on *Strange
Case of Dr Jekyll and Mr Hyde* (about 25,000 words) on the target laptop:

| Component | Result |
|---|---|
| GLiNER2 base + fastcoref, synthetic corpus | 0 misses, 0 false merges, 0 splits; ambiguous titles kept ambiguous |
| Same on Jekyll, 9 annotated characters | 0 misses, 0 false merges; one role-noun split by design; about 4 minutes, 4.4 GB peak |
| Appearance passages | Hand-written patterns recall 0.79 against 0.33 for the zero-shot classifier |
| EmbeddingGemma-300M (sentence-transformers), 25 visual queries | recall@5 0.71, recall@10 0.84; index in under 2 minutes |
| bge-small / BM25 / equal-weight RRF | recall@5 0.63 / 0.55 / 0.64 |
| Local generator (Qwen3 4B) | About 1 token/s; not viable on this hardware |
| PyTorch dynamic int8 | Broke GLiNER2, halved bge-small recall; not a default |
| HHEM-2.1-open | Misses dreams, rumours and denials; useful only as a secondary signal |

## Decision

**Ingestion is local.** No book text leaves the machine during upload,
parsing or narrative extraction:

- Entities and mentions with GLiNER2 base (fp32), clustered by deterministic
  identity rules: one identity per proper name whatever its label; full names
  fold into a surname that occurs alone; a lone first name folds into the single
  full name it starts; titles and role nouns alone stay ambiguous; a stop-list
  removes pronouns and function words tagged as names.
- Pronoun and alias links with fastcoref per chapter; chapters over 40,000
  characters are split into windows of whole passages.
- Appearance-candidate spans with hand-written lexical patterns.
- Search indexes: PostgreSQL full-text plus EmbeddingGemma-300M vectors in
  pgvector, loaded from the official weights through sentence-transformers.
  EmbeddingGemma ranks first; lexical and entity-linked candidates are merged
  with weights chosen by measurement, not equal-weight RRF.

These run as derivation stages behind the existing contracts: versioned
derivations, attempt-guarded publication, verbatim span grounding, rejection
counts and dependency-closure eligibility are unchanged.

**Facts are consolidated at query time from a small, cutoff-filtered set.**
After local retrieval and the reading cutoff, only the selected passages
(target about 20 passages, about 5,000 tokens per question) are sent through
the provider envelope to Groq `gpt-oss-120b` with Zero Data Retention (DEC-36),
using the strict output schema. The adapter honours the provider's
`retry-after` delay instead of retrying immediately. Consolidated facts pass
the existing deterministic gates (attribution, owner, negation and question,
scene) before use; HHEM may lower a fact to non-canonical but never admits one.

**Model pinning.** Every local model is pinned by repository revision, and the
processing version records model revisions, precision and runtime versions. No
quantized model is used unless it matches full precision on the annotated
corpora.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep LLM extraction at ingestion through the FreeLLM gateway | Whole book disclosed to uncontrolled upstreams; nondeterministic routing |
| Whole-book extraction on Groq | Free tier far too small; still discloses the whole book |
| Paid Gemini for extraction | Per-use cost and whole-book disclosure; stays a possible later fallback |
| Local generator for consolidation | 1 token/s on this machine |
| BookNLP | Unmaintained since 2024; book-length coreference over-merges |
| Equal-weight hybrid fusion (ADR-0002 baseline) | Measured lower than EmbeddingGemma alone on the novel |

## Consequences

- Event extraction and partial chronology cannot rely on an ingestion-time LLM.
  Local derivations supply entities, mentions, appearance candidates and
  chapter order; events and facts become query-time claims scoped to the
  question, the reading cutoff and the cited passages. The narrative contract
  and canonical model must be revised before this is implemented.
- ADR-0002 still holds for entity-aware hybrid retrieval and temporal
  grounding; this ADR changes where extraction runs and replaces equal-weight
  fusion with measured weighting. The retrieval strategy is a fixed source
  document; where it differs, this ADR and DEC-37 take precedence.
- DEC-24 (FreeLLM gateway) becomes development-only: synthetic fixtures may use
  it; private books may not.
- Requirements on the machine: about 2.5 GB of model files and about 4.5 GB of
  peak memory during ingestion; a typical novel is expected to take 15–30
  minutes (estimate, scaled from Jekyll).
- Each question costs a few thousand Groq tokens; on the free plan this means
  a small number of questions per minute and a daily cap. OPEN-05 limits must
  account for this.
- Remaining measurements: weighted fusion or a MiniLM reranker over the top 20,
  and a second annotated novel.
