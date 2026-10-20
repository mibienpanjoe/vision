# Development and operations

**Status:** executable local foundation and TXT/Markdown source-ingestion/evidence
checks implemented; narrative reconstruction and richer formats pending.
The CI workflow checks the same foundation commands without deployment or model calls.

## Current repository

The repository contains working specifications, brand assets, a synthetic corpus,
a locked API, generated contracts, local accounts/sessions, a themed web shell,
private text uploads/library/evidence, and durable probe/text-parser workers. PostgreSQL/pgvector and Redis use dedicated loopback
services. The [documentation map](../documentation-map.md) remains the entrypoint
for the product contracts; the commands below own the executable setup.

## Intended local baseline

| Component | Selected technology | Current boundary |
|---|---|---|
| Web | Next.js, TypeScript, Tailwind, shadcn/ui | Themed shell implemented; library/reconstruction screens pending |
| API | Python, FastAPI, Pydantic | Health/auth/probe and text upload/library/evidence implemented; narrative endpoints pending |
| Database | PostgreSQL, pgvector, SQLAlchemy, Alembic | Access, work/document, ingestion, chapters/passages and vector extension; narrative tables pending |
| Jobs | Redis, Dramatiq | Real probe and text parser with bounded retry, cancellation and interrupted-job reconciliation |
| Sources/assets | Private local filesystem | Storage root, permissions, quota and retention |
| Models | Role-specific provider adapters | Installed FreeLLM selected; role/model checks remain before first live consumer |
| Integration | Docker Compose | Pinned private local services and verification commands below |

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
Resolve and commit actual dependencies with their first consumer. T14 added
Docling for PDF parsing without OCR; see [PDF parser runtime](#pdf-parser-runtime--t14).
EPUB parsing (T15) uses lxml and defusedxml from the same group; no OCR engine is approved.
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
name are `vision`. Never commit this file. Use `make setup` below and the secret-free environment field reference.

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
origins only. The consolidated commands below cover clean setup and integration/browser checks.

## Probe worker — T08

Redis is a dedicated, password-protected, digest-pinned service on loopback 56379
with persistent queue data. Private `.env` now includes `REDIS_PASSWORD`,
`REDIS_PORT` and matching `REDIS_URL`. Start it with:

```sh
docker compose up -d --wait redis
cd apps/api
uv run --locked --env-file ../../.env python -m app.workers.dispatch
uv run --locked --env-file ../../.env dramatiq app.workers.bootstrap --processes 1 --threads 1
```

The dispatch command publishes up to 50 pending jobs per transaction until none
are sent; rerun after a broker outage. Worker retries are bounded (two, with
1–5 second backoff); database and Redis calls have two-second connection bounds.
No extra metrics server is started. Broker messages contain job IDs only; source,
credentials and client-selected owners are not payloads. Queue namespace defaults
to `vision`; tests use a unique namespace and disposable PostgreSQL database.

T08 proved an actual Redis→Dramatiq→PostgreSQL result, stopped-worker pending state,
restart, scoped polling, request replay/conflict and failed-publication recovery.
The small probe commits atomically; it does not establish long-running ingestion
crash/cancellation recovery. The [job API](../api/api-contract.md#bounded-worker-probe--t08)
owns response semantics. The consolidated commands below and CI check this foundation.

## Local commands and verification

Prerequisites: Node 24.12.0, pnpm 10.28.0, uv 0.12.15, a running Docker daemon,
and Compose v2-compatible commands. uv selects/manages Python 3.12.14 from the API
pin. From a clean checkout:

```sh
make setup
make dev
```

`make setup` preserves an existing `.env`, or creates it with random local database/
broker secrets and mode 0600. Do not copy the blank credential fields from
[.env.example](../../.env.example) as working credentials. The example documents
configuration fields; generated `.env` and runtime data stay ignored. Dependency
installs use frozen locks and disabled dependency lifecycle scripts. No global
package upgrade or FreeLLM call is part of setup.

`make dev` starts/checks the local database/broker, applies migrations and runs
API, worker and web processes. Open `http://127.0.0.1:3000`; the honest library
shell says uploads are not yet available. Ctrl+C stops the development processes;
`make stop` stops the persistent containers without deleting volumes. The API
binds loopback 8000, PostgreSQL 55432 and Redis 56379. The command is local-only.

| Command | Purpose |
|---|---|
| `make services migrate` | Start/check PostgreSQL/Redis and apply migrations |
| `make api`, `make worker`, `make web` | Run one service separately in its own terminal |
| `make dispatch` | Reconcile pending probe and ingestion queue publication after a broker outage |
| `make reconcile-sources` | Remove old, unreferenced interrupted originals; preserve active/linked sources |
| `make browsers` | Install the isolated Chromium browser; OS browser prerequisites may be required |
| `make check` | Repository lint, non-infrastructure tests, deterministic contract regeneration, Node/type checks, web build and shell browser checks, documentation checks |
| `make integration` | Real authenticated PostgreSQL/Redis/worker tests in disposable databases and unique queue namespaces |
| `make browser-session` | Real API and Chromium cookie transport through the web proxy, using a disposable database/account |
| `pnpm audit --audit-level=high` | Native JavaScript known-advisory check; not a general security proof |

Run `make services migrate` and `make browsers` before the browser/infrastructure
checks. Session-browser verification requires loopback 8000 and 13000 to be free;
it starts/stops its own API and web test processes. Unit-only runs deliberately
exclude marked infrastructure tests; the CI and full foundation check run both.
The PostgreSQL fixture uses the configured development administrator only to
create isolated `vision_test_*` databases, then removes those test databases.
Tests never clear the reader's database or flush shared Redis. The browser
harness provisions only a synthetic test account and cleans its API/database.

The [CI workflow](../../.github/workflows/ci.yml) uses pinned action commits,
read-only repository permission and generated disposable service credentials.
It executes these same commands plus the advisory audit; live model/paid tests
are absent. Only its own ephemeral CI volumes are removed at job end. A separate
local clone with distinct ports/service project passed the documented clean-setup
sequence; exact run evidence remains in the task/PR record. No external deployment,
provider quality or book reconstruction follows from these foundation checks.


## Private original storage — T10

Originals default to ignored `storage/originals/` outside public web roots.
`VISION_SOURCE_ROOT` can select another private local directory for API and
future ingestion workers; use the same path for both roles. The directory must
have no group/other permissions (0700); files are created 0600. Generated random
references never include uploaded filenames. Do not point this root at a web
server's public directory or a shared/private-book directory owned by another app.

`make reconcile-sources` scans only generated source names, skips symlinks and
active leases, and checks PostgreSQL before removing unreferenced files at least
one hour old. Run it after interrupted uploads or uncertain database commits.
It is interrupted-upload cleanup, not reader-requested deletion or retention.
Those lifecycles remain with their later tasks. Text-ingestion intents use their
own queue/consumer; `make dispatch` reconciles both probe and ingestion
publication. The worker verifies the retained source fingerprint before parsing.


## PDF parser runtime — T14

The API project's default `pdf` dependency group installs Docling 2.140.0,
lxml and defusedxml, with CPU-only PyTorch from the PyTorch CPU index, so no
CUDA wheels are installed.
The environment grows to about 1.5 GB. Only the worker imports Docling.

`make setup` downloads Docling's Heron layout model (about 330 MB, Apache-2.0)
once into ignored `.local/docling-models`. Workers read it from
`VISION_DOCLING_ARTIFACTS` (default: that directory) and never download at
parse time. If a download was interrupted, delete the directory and rerun
`make setup`. Conversions run one at a time per worker process. On the
development CPU a five-page fixture takes about 10 seconds, including model
load; book-length timing is not yet measured. CI allows 25 minutes for the
larger install. The model files are fetched by Docling's own downloader and not
redistributed by this repository.
