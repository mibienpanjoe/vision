# Development and operations

**Status:** preparation requirements; no executable development setup or deployment.

## Current repository

The repository contains source briefs, working documentation, and brand assets.
There are no dependency manifests, environment template, database migrations,
Compose services, application commands, tests, or CI workflows. Reading the
[documentation map](../documentation-map.md) is the current starting action.
Do not run invented `npm`, `uv`, migration, or Compose commands from the brief's
planned directory tree.

## Intended local baseline

| Component | Selected technology | Setup still required |
|---|---|---|
| Web | Next.js, TypeScript, Tailwind, shadcn/ui | Runtime/package versions, manifests, app shell |
| API | Python, FastAPI, Pydantic | Runtime/dependency versions, app and configuration |
| Database | PostgreSQL, pgvector, SQLAlchemy, Alembic | Image/version, schema, search configuration, migrations |
| Jobs | Redis, Dramatiq | Broker/worker settings, durable attempts, cancellation and recovery |
| Sources/assets | Private local filesystem | Storage root, permissions, quota and retention |
| Models | Role-specific provider adapters | Provider/model selection, credentials, data handling, budgets |
| Integration | Docker Compose | Service definitions, health checks, ports, volumes |

The first executable setup change must document actual prerequisites, pinned
versions, environment variables, startup/stop/reset commands, migration order,
synthetic seed inputs, checks, and expected health results here. Destructive
database resets must be distinguished from routine startup. Commit only a
secret-free environment example.

## Durable processing and visibility

The [ingestion contract](../ingestion/ingestion-contract.md) owns lifecycle
semantics. PostgreSQL records attempts and outcomes; Redis queue state alone is
not a job history. Emit safe correlation IDs and processing versions through
API, worker, model calls, reconstruction, and render attempts.

Record stage durations, retries, safe failures, parser coverage, candidate
counts, grounding rejection counts, and model usage. Logs should make a failure
diagnosable without routinely retaining book passages or secrets.

On interruption, determine the durable outcome before retrying effects. A worker
redelivery may resume or reuse completed units but cannot duplicate canonical
facts or charge for an unnecessary image silently. Exact idempotency keys,
lease/recovery mechanisms, and provider retry policy are not yet chosen.

## Reprocessing and restoration

Version parsing, extraction, embeddings, retrieval, prompts, and schema inputs.
Do not mix incompatible embeddings or reuse a state from another generation,
owner, cutoff, moment, or creative mode. Restore databases and source storage
together so citations still resolve; restore indexes from compatible versions
or explicitly rebuild them. Retention and deletion need a defined policy before
real users depend on persisted evidence.

## Deployment gate

The selected deployment storage is S3-compatible, but no host/provider has been
chosen. Before external deployment resolve authorization, TLS/network exposure,
upload and model budgets, secret management, worker shutdown/recovery, backup
restoration, source/provider retention, and monitoring. Exercise the real
browser/API/database/worker path in that environment. Local documentation checks
and fixture tests are not evidence of deployment readiness.
