# Development and operations

**Status:** T04 API/PostgreSQL bootstrap verified locally; remaining Phase 1 tasks pending.

## Current repository

The repository contains working specifications, brand assets, a synthetic corpus,
and the first locked API/health implementation. The database service and
migration bootstrap are implemented; web, authentication, workers and CI follow.
Reading the
[documentation map](../documentation-map.md) is the current starting action.
Do not run invented `npm`, `uv`, migration, or Compose commands from the brief's
planned directory tree.

## Intended local baseline

| Component | Selected technology | Setup still required |
|---|---|---|
| Web | Next.js, TypeScript, Tailwind, shadcn/ui | Manifests, app shell; runtime/package tools selected below |
| API | Python, FastAPI, Pydantic | Dependency locks, app and configuration; runtime selected below |
| Database | PostgreSQL, pgvector, SQLAlchemy, Alembic | Schema, search configuration, migrations; image selected below |
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
metadata resolution, not an API lock, installation or parser execution.
Resolve and commit actual dependencies with their first consumer. Keep Docling's heavy conversion dependencies out of the API bootstrap
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

**Outside current scope:** DEC-25 selects local-only operation. The original
external-deployment considerations below are retained for a future scope change.

The selected deployment storage is S3-compatible, but no host/provider has been
chosen. Before external deployment resolve authorization, TLS/network exposure,
upload and model budgets, secret management, worker shutdown/recovery, backup
restoration, source/provider retention, and monitoring. Exercise the real
browser/API/database/worker path in that environment. Local documentation checks
and fixture tests are not evidence of deployment readiness.

## Local model gateway

The maintainer selected the installed **FreeLLM API** for LLM calls (DEC-24).
The existing gateway was observed healthy on loopback port 3001 during Phase 1
prerequisite inspection. Its role/model capabilities, structured outputs,
embeddings, authentication, upstream source-text handling and limits still need
verification before their first consumer. Reuse this installation; no replacement
gateway or external provider account is required. No model call is needed for
Phase 1. Keep configuration/secrets private and record safe model/gateway lineage.

## Delivery scope

The application will run locally, per DEC-25. Bind services to loopback and use
private local file storage. External hosting, domains, deployment and active
S3-compatible storage integration are outside the current delivery. The earlier
deployment direction is retained above for context. Local ownership, untrusted
input safeguards, bounded model work, backup/restore, retention/deletion and
worker recovery remain required. Later packaging and acceptance tasks target a
reproducible local environment. Rendering is optional and needs its own capability
check; selecting FreeLLM does not establish image support. No existing data or
schema migration is required by these decisions.

## API and database bootstrap — T04

Use the selected Python/uv versions above. Backend dependency installation and
health tests now exist:

```sh
uv sync --project apps/api --locked
uv run --project apps/api pytest apps/api/tests -q
```

The local private `.env` contains `POSTGRES_PASSWORD` (a random hex secret),
`POSTGRES_PORT=55432`, and `DATABASE_URL` using the same credentials with the
`postgresql+psycopg` driver and `127.0.0.1:55432/vision`. The database user and
name are `vision`. Never commit this file. T09 provides the consolidated setup
command and secret-free environment example.

With that private environment prepared, the T04 startup sequence is:

```sh
docker compose up -d --wait db
set -a
. ./.env
set +a
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
cd apps/api
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`/health/live` reports process liveness independently of the database.
`/health/ready` requires a real database query and the vector extension; an absent
configuration, unavailable database or missing extension returns safe `503`
unready. It does not claim narrative/search readiness. Migration 0001 installs
vector and the migration-version table; domain tables arrive with consumers.
The lifespan owns/disposes the engine; connection and statement timeouts bound
health checks. See [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
and [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

Routine database stop is `docker compose stop db`; restart with the startup
command. Do not use volume deletion as a restart: it would discard local data.
T04 verified PostgreSQL 17.11 and vector 0.8.7, migration 0001 on a fresh local
database, actual HTTP liveness/readiness 200/200, and DB-down liveness/readiness
200/503 with safe responses. The isolated probe restarted Vision's database and
shut down its temporary API process. Domain tables and integration CI follow.

## Local account administration

After database migration, provision a local account from the API directory:

```sh
cd apps/api
uv run --locked --env-file ../../.env python -m app.cli create-user reader
```

The CLI prompts for a passphrase without echo. `--password-stdin` is available
for isolated test automation; never put credentials in command arguments or
commit them. Duplicate usernames fail safely. API session transport and current
limits are owned by the [authentication contract](../api/api-contract.md#local-authentication--t07).
The web proxy defaults to `http://127.0.0.1:8000`; set `VISION_API_ORIGIN` before
building when selecting a different loopback API port. It accepts loopback HTTP
origins only. T09 consolidates clean-checkout and integration/browser commands.
