# ADR-0002 — Entity-aware hybrid retrieval and temporal grounding

**Status:** accepted baseline, implementation pending.
**Recorded:** 2026-10-19.
**Source:** retrieval strategy, explicitly selected architecture.

## Context

Visual descriptions can be scattered, indirect, attributed to different
subjects, or changed by story events. Chapter order can differ from story time.
A semantic match alone cannot establish a fact's owner, temporal applicability,
or admissibility under the reading boundary.

## Decision

Combine entity-linked evidence, PostgreSQL lexical retrieval, and pgvector
semantic retrieval. Use deduplication and reciprocal rank fusion, preserve
protected canonical evidence, rerank for context, consolidate source claims,
reconstruct the applicable narrative state, and verify each visual attribute
before composing structured JSON.

The source-linked narrative model stores identities, mentions, events, partial
chronology, visual claims, and provenance. It is a revisable derived index, not
an authority replacing the original passage. Apply owner and reading boundaries
to source material and derived decisions.

The [retrieval strategy](../architecture/retrieval-strategy.md) owns the detailed pipeline.

## Alternatives and exclusions

The baseline rejects generic top-k-only RAG, PageIndex, a graph database, and
standalone vector/search infrastructure. These are not parallel experimental
products to implement for an A/B comparison.

## Consequences

Ingestion must do more than chunk and embed text. Provenance, partial ordering,
support type, context, conflicts, and dependency-aware spoiler filtering are
necessary data. Ranks order candidates but do not prove truth. Source-span
checks and temporal reconstruction require dedicated acceptance fixtures.

Ambiguity can produce context choices or explicit uncertainty instead of one
invented portrait. Budgeted retrieval must preserve protected facts without
silently overflowing model context; selection/compression policy must expose
coverage limits. Revisit this architecture only with new evidence and a recorded
decision, not because an alternative framework is available.
