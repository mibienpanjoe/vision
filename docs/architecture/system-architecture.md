# System architecture

**Status:** chosen baseline; module contracts and deployment packaging unimplemented.
**Decisions:** [ADR-0001](../adr/0001-modular-monolith.md),
[ADR-0002](../adr/0002-temporal-hybrid-retrieval.md).

## Context and runtime

```text
Authorized reader
  → Next.js web application
      → FastAPI REST boundary
          → domain services → PostgreSQL (relational + FTS + pgvector)
          → private object storage (local development / S3-compatible deployment)
          → Redis → Dramatiq workers → the same domain services
          → provider adapters → extraction/reasoning/embedding/reranking/image APIs
```

The backend is a modular monolith, not independently deployed domain
microservices. A worker is an execution role using backend domain services;
it does not change domain ownership. Docker Compose is the selected local
baseline. No Compose file or external deployment exists yet.

## Responsibilities and dependencies

| Area | Owns | Boundary |
|---|---|---|
| API / access | Request validation, authorized work scope, resource outcomes | Authentication choice open; routes do not implement narrative logic |
| Ingestion | Source objects, parsing, segmentation, durable ingestion runs | Does not turn unsupported extraction into canon |
| Narrative | Entity mentions/aliases, events, chronology, atomic visual facts | Does not compose artistic prompts |
| Retrieval | Query plans, entity/FTS/vector candidates, fusion, reranking | Ranking does not establish truth |
| Reconstruction | Appearance state for a subject, moment, context, cutoff | Cannot fabricate chronology or use ineligible dependencies |
| Verification | Source-span, attribution, modality, temporal and scope gates | Applies before canonical export and provider prompt composition |
| Visualization | Structured specification, revisions, history, optional rendering | Images are artifacts, not evidence |
| Providers | Role-specific calls, validation, usage, safe failures | No domain ownership or direct canonical writes |
| Workers / infrastructure | Scheduling, attempt execution, storage, DB, telemetry | Domain services remain the behavior owner |

Allowed high-level flow:

```text
ingestion → narrative/indexes
query → retrieval → consolidation → reconstruction → verification → visualization
```

Shared technical helpers stay free of narrative rules. Services communicate
through explicit typed inputs/results rather than accessing another module's
private implementation. Pydantic and generated JSON Schema/OpenAPI are the
future source for shared TypeScript contracts.

## Persistence and search

The [canonical model](../data/canonical-model.md) owns objects and lineage.
PostgreSQL relational structure holds scope, provenance, events, and identity;
JSONB holds flexible attributes/specifications. Full-text indexes preserve
names and use language-aware configurations. pgvector embeddings retain model,
dimension, and generation. ANN strategy follows measured collection needs.

Redis transports background work; durable job status belongs in PostgreSQL.
Do not assume broker delivery is exactly once. Cross-system storage/job/index
effects need idempotence and recovery, detailed when executable contracts land.

## Provider seams

Define narrow operations for extraction, reasoning/consolidation, embeddings,
reranking, and optional rendering. Each receives authorized, bounded input and
returns validated output or a safe typed failure, plus model/configuration and
usage metadata. Provider-specific payloads do not leak into domain storage as
the only representation of a fact.

Deterministic adapters make contract tests reproducible; they are not proof of
live extraction quality. Every live role needs source handling, timeout, retry,
and budget choices before use. Do not select models implicitly in documentation.

## Intended repository layout

```text
apps/web/                    Next.js workspace (planned)
apps/api/app/api/v1/          REST routes (planned)
apps/api/app/services/        ingestion, narrative, retrieval,
                              reconstruction, verification, visualization
apps/api/app/providers/       replaceable AI adapters
apps/api/app/workers/         Dramatiq entry points
apps/api/migrations/          Alembic schema history
apps/api/tests/               backend tests and synthetic fixtures
packages/contracts/          generated TypeScript / schema contracts
infrastructure/docker/       container definitions
docs/                        working specifications
```

Only documentation and brand assets exist in this increment. The overview and
detailed retrieval strategy are classified under `docs/product/` and
`docs/architecture/`, respectively; the application paths above remain planned.

## Trust and operational boundaries

Follow [security](../../SECURITY.md) at every entry point, including jobs,
provider calls, caches, evidence, and asset downloads. Source cutoff is a
semantic information boundary in addition to owner authorization. Operational
visibility, cancellation, reprocessing, and readiness gates are owned by
[development and operations](../operations/development-and-operations.md).
