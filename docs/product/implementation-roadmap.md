# Implementation roadmap

**Status:** milestones 1–3 have local implementation and acceptance evidence.
The order derives from overview §12 and the accepted phase plan; optional
rendering and release/operations gates remain open. The
[acceptance strategy](../testing/acceptance-strategy.md) owns the evidence and
measured model-quality limits; local acceptance does not establish deployment readiness.
This document owns milestone scope, not a second requirement list.

## Milestone 1 — Narrative representation

Start with one small synthetic TXT/Markdown work containing aliases, a later
flashback, a wartime injury, two clothing contexts, and a contradictory claim.
Establish the development skeleton, work ownership, durable upload/job state,
immutable parsed passages, and source-linked entity/event/fact storage. Then add
PDF and EPUB adapters, handling degraded structure explicitly.

**Gate:** follow a stored fact to its exact source span; reprocess without breaking
an old citation; reject an unauthorized work read. Compare extraction with a
manually annotated fixture. A parser-only demonstration does not complete this
milestone's narrative representation.

## Milestone 2 — Retrieval and reconstruction

Implement the selected entity/lexical/vector pipeline, protected evidence,
fusion and reranking, partial chronology, scoped reconstruction, verification,
and typed visual JSON. Apply DEC-22 and the selected first wire conventions before
treating their behavior as stable.

**Gate:** the same entity yields correct childhood/battle/home states with exact
citations; future-only and out-of-cutoff knowledge is excluded; contradictions
remain visible; a schema-valid but unsupported claim is rejected. Include one
live provider path separately from deterministic adapter tests.

## Milestone 3 — Product experience

Build the library, ingestion status, entity/context exploration, reconstruction
workspace, evidence reader, JSON export and revision-safe presentation refinement.
Use shadcn/ui and selectively adapt agent-interface components to the existing
domain outcomes, following DEC-13 and the component-origin gate.

**Gate:** in a real browser, upload → status → entity/context → reconstruction →
attribute → source span → export completes against the actual API and database.
Exercise narrow layouts, keyboard access, ambiguity, insufficient evidence,
failed jobs, and boundary changes. Do not count a static mockup as this gate.

## Milestone 4 — Rendered visuals

Add an image-provider adapter, rendering job outcomes, image/specification
linkage, history, and creative refinement preserving locked facts.

**Gate:** a real render references a validated specification and selected
provider/model; failures and retries are visible; an image never creates canon.
Brand asset generation during documentation is separate from this product feature.

## Milestone 5 — Operational hardening

Complete deployment packaging, backup/restore, controlled reprocessing,
performance tuning, limits, telemetry, recovery, and provider cost controls.
Foundational ownership, upload validation, and versioning start in milestone 1;
they are not postponed to this stage.

**Gate:** demonstrate recovery and authorization in the intended deployment,
resolve the relevant open operations decisions, and record the scope of actual
load and end-to-end checks. No delivery dates or throughput promises are fixed.

## Working method

Choose a small vertical increment within a milestone, define its evidence, and
verify it before claiming completion. Keep temporary task breakdowns under the
ignored `tasks/` directory. Update requirements or decisions when behavior
changes; do not maintain parallel status logs throughout the documentation.
