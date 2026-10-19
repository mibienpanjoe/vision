# Development and operations

**Status:** T01 toolchain selected; no executable application setup or deployment.

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

## Selected toolchain — D0

Selected on 2026-10-19 for the first implementation. These are reproducible
starting versions, not a claim that the application runs or that every parser
format has passed acceptance. Review security/patch updates before deployment.

| Component | First implementation choice | Reproducibility |
|---|---|---|
| Python | CPython 3.12.14, project range `>=3.12,<3.13` | Pin `.python-version` with the API manifest in T04; use the managed interpreter rather than the machine default 3.14 |
| Python packages | uv 0.12.15 | Commit generated `uv.lock`; use `uv sync --locked` in automated checks |
| Web runtime | Node.js 24.12.0, Next.js 16 family, TypeScript 5 family | T05 pins the runtime and exact direct dependencies in its manifest and generated lock |
| JavaScript packages | pnpm 10.28.0 | Exact `packageManager` field, committed `pnpm-lock.yaml`, `pnpm install --frozen-lockfile` |
| Database | PostgreSQL 17 + pgvector 0.8.7 on Bookworm | Pin the image digest below in T04; query server and extension versions on actual startup |
| Broker | Redis 8.2.10 on Bookworm | Pin the image digest below in T08; prove broker/worker behavior there |
| Local services | Docker Engine 29.9.1 and Compose v5.6.0 observed | Compose v2-compatible service configuration; do not depend on v5-only features |

Selected image references (multi-platform index digests verified from the
registry; tags alone are not the immutable identity):

```text
pgvector/pgvector:0.8.7-pg17-bookworm@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
redis:8.2.10-bookworm@sha256:47670742d7924adbcdb404d1288b6327815b23141969c0939b8e5d61f78c2634
```

Python 3.12 is supported through October 2028 and gives the parser/native-wheel
stack a conservative common runtime. Node 24 is an LTS line and exceeds
Next.js 16's Node 20.9 minimum. PostgreSQL 17 is supported through November 2029;
pgvector supports PostgreSQL 13+. These support facts do not prove compatibility
of a specific resolved application dependency graph.

Prerequisite inspection found Python 3.12.14, uv 0.12.15, Node 24.12.0,
pnpm 10.28.0, Docker 29.9.1, and Compose v5.6.0. The Docker daemon answered its
version query. Host `psql` is absent; use the database container's client in T04.
No services were started and no packages were installed for T01.

The parser candidate is Docling 2.140.0 (Python metadata `>=3.10,<4.0`).
A binary-only Linux x86_64/Python 3.12 dependency-resolution probe includes
FastAPI 0.147.0, SQLAlchemy 2.1.5, Alembic 1.20.0 and Dramatiq/Redis 2.2.1.
The probe passed with binary distributions for the selected target; this is
metadata resolution, not an API lock, installation or parser execution. Resolve and commit actual dependencies with their first
consumer. Keep Docling's heavy conversion dependencies out of the API bootstrap
until its parser task requires them. PDF extraction/OCR and EPUB mapping still
need T14/T15 format fixtures; no OCR engine or model assets are approved here.
Embedding dimension/model, ANN tuning, provider choices and resource budgets
remain open at their owning gates. There is no existing database to migrate.

Official sources used for this choice:

- [Python support status](https://devguide.python.org/versions/)
- [Node release status](https://nodejs.org/en/about/previous-releases)
- [Next.js 16 runtime requirements](https://nextjs.org/docs/app/guides/upgrading/version-16)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [pnpm frozen installation](https://pnpm.io/cli/install)
- [PostgreSQL version policy](https://www.postgresql.org/support/versioning/)
- [pgvector compatibility and Docker images](https://github.com/pgvector/pgvector)
- [Redis official image source](https://github.com/redis/docker-library-redis)
- [Docling 2.140.0 release](https://github.com/docling-project/docling/releases/tag/v2.140.0)

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
