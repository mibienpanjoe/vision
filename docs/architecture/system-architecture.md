# System architecture

**Status:** local API, web shell, access and worker foundation implemented;
narrative pipeline and local application packaging remain planned.
**Decisions:** [ADR-0001](../adr/0001-modular-monolith.md),
[ADR-0002](../adr/0002-temporal-hybrid-retrieval.md).

## Context and runtime

```text
Authorized reader
  → Next.js web application
      → FastAPI REST boundary
          → domain services → PostgreSQL (relational + FTS + pgvector)
          → private local object storage (planned)
          → Redis → Dramatiq workers → the same domain services
          → provider adapters → extraction/reasoning/embedding/reranking/image APIs
```

The backend is a modular monolith, not independently deployed domain
microservices. A worker is an execution role using backend domain services;
it does not change domain ownership. Docker Compose is the selected local
baseline: Compose runs PostgreSQL/pgvector and Redis, while API, web and worker
processes run on the host. External deployment is excluded by DEC-25.

## Responsibilities and dependencies

| Area | Owns | Boundary |
|---|---|---|
| API / access | Request validation, authorized work scope, resource outcomes | Local sessions selected in DEC-26; routes do not implement narrative logic |
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
private implementation. Pydantic and generated JSON Schema own the implemented
shared TypeScript contracts; FastAPI exposes the executable route OpenAPI schema.

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

### Provider envelope — T17

`app/providers/contracts.py` defines a frozen `ProviderRequest` (role, purpose,
prompt version, system-owned instructions, up to 64 quoted `SourceItem`s and
`Limits`) and rejects unknown fields, so a request cannot carry tools,
credentials or scope. `compose` puts the instructions plus a fixed
untrusted-data notice in the system text and the sources only in a JSON data
block; an adapter receives that `ProviderCall` (system, data, output schema,
output-token and time bounds) and nothing else. Outputs subclass
`StructuredOutput` (`extra="forbid"`, strict types, a `schema_version`).

`app/providers/execution.py` returns either the validated output with outcome
`succeeded` or no value with one of `invalid_output`, `timeout`,
`budget_exhausted`, `cancelled`, `provider_unavailable` or `input_too_large`.
Oversized input and cancellation before the call skip the adapter; cancellation,
elapsed time or token budget exceeded after the call discard the response.
Execution has no side effects: the caller persists the safe `RunRecord` with
`persist_run` in the same transaction as any canonical write, so malformed or
discarded output cannot reach canon. Default limits (60 s, 48,000 input
characters, 2,048 output and 16,000 total tokens) are T17 engineering bounds
under OPEN-05. `ScriptedAdapter` and `RuleAdapter` are the deterministic
adapters. T18 adds `ChatGateway` (`app/providers/openai_compatible.py`), an
OpenAI-compatible chat adapter for the local FreeLLM gateway (DEC-24): JSON
object mode, temperature 0, the output schema appended to the system text, no
tools, and HTTP/timeout failures mapped to the typed outcomes. It is disabled
unless `VISION_LLM_API_KEY` is set; the routed model name returned by the
gateway is recorded as `model_version`. On 2026-10-20 the opt-in live test ran
entity extraction on the synthetic corpus through `auto` routing: five chapter
batches succeeded after bounded retries (one timeout, one unavailable route),
with 0 misses, 0 false merges, 0 splits and 0 ambiguity violations against the
annotations, plus unannotated object entities. Routed models varied per call
(e.g. qwen3.8-27b, gpt-oss-120b, Gemini variants), so results are not
reproducible by model name; a pinned model was unavailable upstream at the time.

## Repository layout and remaining modules

```text
apps/web/                    Next.js themed shell
apps/api/app/api/v1/          authentication and probe-job routes
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

The shell, access boundary, durable probe-job service, worker entry points,
Alembic migrations, generated contracts and foundation tests exist, as do
ingestion and the provider envelope with deterministic adapters. Narrative,
retrieval, reconstruction, visualization and live provider adapters remain
planned. See the
[operations guide](../operations/development-and-operations.md) for the runnable
foundation and its verification commands.

## Trust and operational boundaries

Follow [security](../../SECURITY.md) at every entry point, including jobs,
provider calls, caches, evidence, and asset downloads. Source cutoff is a
semantic information boundary in addition to owner authorization. Operational
visibility, cancellation, reprocessing, and readiness gates are owned by
[development and operations](../operations/development-and-operations.md).
