# Development and operations

**Status:** local product, packaging, deletion and recovery implemented.
Final acceptance is scoped in the [acceptance strategy](../testing/acceptance-strategy.md).
CI runs the automated regressions; live provider calls and packaged local-model
drills have separate opt-in evidence.

## Current repository

The repository contains working specifications, brand assets, a synthetic corpus,
a locked API, generated contracts, local accounts/sessions, the browser product
workspace, four-format ingestion, scoped reconstruction, optional private image
rendering and durable processing/deletion workers. PostgreSQL/pgvector and Redis use dedicated loopback
services. The [documentation map](../documentation-map.md) remains the entrypoint
for the product contracts; the commands below own the executable setup.

## Intended local baseline

| Component | Selected technology | Current boundary |
|---|---|---|
| Web | Next.js, TypeScript, Tailwind, shadcn/ui | Library, scoped explorer, source reader, reconstruction/export, refinement and render history |
| API | Python, FastAPI, Pydantic | Authenticated owned resources, revision/idempotency guards and safe outcomes |
| Database | PostgreSQL, pgvector, SQLAlchemy, Alembic | Versioned sources, narrative/index derivations, specifications, render lineage and deletion tombstones |
| Jobs | Redis, Dramatiq | Ingestion, narrative, rendering and deletion with durable SQL intent and recovery |
| Sources/assets | Private local filesystem | Opaque originals/images, owner-only permissions, deletion and offline snapshots |
| Models | Role-specific provider adapters | Local extraction/embeddings, Groq query-time consolidation and optional configured image providers |
| Integration | Docker Compose | Pinned services and reproducible local API/worker/web images |

Setup and recovery commands below preserve private runtime data. Database/volume
removal is a destructive reset, separate from routine startup and from restoring
into a new target. Commit only a secret-free environment example.

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
facts or charge for an unnecessary image silently. SQL intent, advisory execution
leases and bounded attempts implement these rules. Interrupted image claims
settle as acceptance unknown; the [restore procedure](#backup-and-restoration--t47)
also treats queued snapshot image attempts conservatively.

## Reprocessing and restoration

Version parsing, extraction, embeddings, retrieval, prompts, and schema inputs.
Do not mix incompatible embeddings or reuse a state from another generation,
owner, cutoff, moment, or creative mode. Restore databases and source storage
together so citations still resolve; restore indexes from compatible versions
or explicitly rebuild them. [Book deletion](#work-retention-and-deletion--t46)
and [offline restoration](#backup-and-restoration--t47) define the implemented
local lifecycle; account deletion and automatic expiry remain outside it.

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
Since DEC-37 it may process synthetic fixtures only, never a private book;
private-book processing is local, and query-time excerpts go to Groq with Zero
Data Retention ([ADR-0003](../adr/0003-local-ingestion-minimal-disclosure.md)).

Local extraction installs with the default `narrative` dependency group
(GLiNER2, fastcoref, sentence-transformers; transformers is held below 5 because
fastcoref fails on it). The pinned model revisions download once into the
Hugging Face cache (`HF_HOME`, about 1 GB for entities and 1.2 GB for
EmbeddingGemma); only model files are fetched, never book text. EmbeddingGemma
is gated: accept the Gemma licence on Hugging Face and set `HF_TOKEN` in `.env`
for the first download, after which `HF_HUB_OFFLINE=1` works. The real-model
tests are opt-in:

```sh
set -a; . ./.env; set +a
VISION_LOCAL_MODELS=1 VISION_TEST_ADMIN_URL=$DATABASE_URL \
  uv run --project apps/api --locked pytest apps/api/tests/test_local_entities.py \
  apps/api/tests/test_semantic_integration.py -m integration -s
```
The existing gateway was observed healthy on loopback port 3001 during Phase 1
prerequisite inspection. Its role/model capabilities, structured outputs,
embeddings, authentication, upstream source-text handling and limits still need
verification before their first consumer. Reuse this installation; no replacement
gateway or external provider account is required. No model call is needed for
Phase 1. Keep configuration/secrets private and record safe model/gateway lineage.

Vision reads `VISION_LLM_API_KEY` (the gateway's unified key, from its Keys
page), `VISION_LLM_BASE_URL` (default `http://127.0.0.1:3001/v1`) and
`VISION_LLM_MODEL` (default `auto`) from the private `.env`. Without the key no
live adapter is constructed. The live extraction test runs only when explicitly
requested, so `make integration` never calls the gateway:

```sh
set -a; . ./.env; set +a
VISION_LIVE_PROVIDER=1 VISION_TEST_ADMIN_URL=$DATABASE_URL \
  uv run --project apps/api --locked pytest apps/api/tests/test_entity_extraction.py -k live -m integration -s
```
 The
gateway forwards requests to whichever upstream free provider it routes to, so
any text sent leaves the machine; only the synthetic corpus may be sent until
provider data handling is recorded (SECURITY.md, OPEN-02).

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
`/health/ready` requires a real database query, the vector extension and
owner-only, writable original and render roots (T45); an absent configuration,
unavailable database, missing extension or unusable storage returns safe `503`
unready. Redis is not required: a failed enqueue stays visibly pending in SQL. It does not claim narrative/search readiness. Migration 0001 installs
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
API, worker and web processes. Open `http://127.0.0.1:3000` and sign in with a
locally provisioned account to upload a book. Ctrl+C stops the development processes;
`make stop` stops the persistent containers without deleting volumes. The API
binds loopback 8000, PostgreSQL 55432 and Redis 56379. The command is local-only.

| Command | Purpose |
|---|---|
| `make services migrate` | Start/check PostgreSQL/Redis and apply migrations |
| `make api`, `make worker`, `make web` | Run one service separately in its own terminal |
| `make dispatch` | Reconcile pending probe, ingestion, narrative, render and deletion queue publication after a broker outage; recover interrupted processing and cleanup; settle unheld running render jobs as `acceptance_unknown` |
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


## Image rendering — DEC-51

Rendering is off by default. To enable it, set `VISION_RENDER_PROVIDER` in the
private `.env`:

- `openai` with `OPENAI_API_KEY`: `gpt-image-2` by default, or `gpt-image-1` with
  `VISION_RENDER_MODEL=gpt-image-1`; low quality, 1024×1024 PNG at
  `https://api.openai.com/v1/images/generations`, billed to that OpenAI project.
  Any other model leaves rendering disabled.
- `huggingface` with `HF_TOKEN`: `black-forest-labs/FLUX.1-schnell` at
  `https://router.huggingface.co/nscale/v1/images/generations`, billed to that
  account's Inference Provider credit. The token must be fine-grained with
  permission to call Inference Providers; a read-only download token fails as
  `PROVIDER_UNAUTHORIZED`, an account without credit as `PROVIDER_QUOTA_EXCEEDED`.

Rendered images
default to ignored `storage/renders/`, or `VISION_RENDER_ROOT`, with the same
private-directory rules as originals. Each owner may reserve five renders.

The live acceptance request is opt-in and counts toward DEC-51's five-request
acceptance budget; record each run with the task evidence:

```sh
set -a; . ./.env; set +a
VISION_LIVE_RENDER=1 VISION_TEST_ADMIN_URL=$DATABASE_URL \
  uv run --project apps/api --locked pytest apps/api/tests/test_live_render.py -m integration -s
```

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
own queue/consumer; `make dispatch` reconciles probe, ingestion and narrative
publication. Narrative jobs run locally by default; `VISION_NARRATIVE_PROVIDER=live`
switches the worker to gateway extraction, which is for synthetic text only
(DEC-37), and `off` disables narrative jobs. The worker verifies the retained source fingerprint before parsing.


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

## Library browser harness — T34

After `make services` and a current `pnpm --dir apps/web build`, run:

```sh
VISION_TEST_LIBRARY=1 make browser-session
```

The harness creates a disposable database, private source directory and unique
Redis namespace, provisions two synthetic accounts, and starts an isolated API
on port 8000 plus a real ingestion-only Dramatiq worker. Playwright serves the
built web app on port 13000. These ports must be free. The suite pauses only its
own worker process group for queued cancellation, then resumes it in cleanup.
A test-only bootstrap adds a file gate before the real parse call for running
cancellation; no test hook enters production code.
The harness removes its database, sources and Redis keys afterward. It does not
modify the developer's library or run external models. Logs and screenshots stay
in `.local/`. The standard `make browser-session` retains its session-transport
check; the library option adds the controls and lifecycle acceptance cases.

For scoped exploration and persisted context checks, use
`VISION_TEST_WORKSPACE=1 make browser-session`. This starts both worker queues
with deterministic model adapters, and a test-only API bootstrap supplies
deterministic consolidation/adjudication. Production code has no fixture switch;
the test modules are selected explicitly by the harness. No live model is called.

The workspace harness includes accessibility, explorer, evidence, reconstruction
and two-tab refinement/history tests.
`VISION_TEST_WORKSPACE_SPECS` can select specific Playwright files. If another
local service uses port 8000, choose a dedicated test API port and build the web
proxy for that same origin, for example:

```sh
VISION_API_ORIGIN=http://127.0.0.1:18000 pnpm --dir apps/web build
VISION_TEST_API_PORT=18000 VISION_TEST_WORKSPACE=1 make browser-session
```

A later normal build uses the default API origin again; never exercise a test
harness against an unrelated listener or a build with a different proxy target.

For the explicit live product gate, use
`VISION_TEST_LIVE_WORKSPACE=1 make browser-session` (with the same port override
when needed). It uses the production API and worker bootstraps, pinned local
entity/coreference/embedding models and the configured Groq adapter, never the
fixture adapters. Only the committed synthetic story is uploaded. This opt-in
loads provider configuration from the private `.env`; Groq must be configured,
and model snapshots must already be cached. `HF_HUB_OFFLINE=1` prevents implicit
model downloads; set `HF_HOME` if the snapshots use a separate cache directory.
The test inspects the stored specification, source highlights and identical JSON
export; the harness additionally asserts successful local/Groq run records,
persisted vectors and revisions before removing its disposable data. CI uses the
deterministic workspace suite and does not require provider credentials.

The web rewrite proxy has a bounded 300-second timeout. The framework's default
30 seconds can close a cold local embedding query followed by consolidation
(90-second provider budget) and adjudication (60-second budget). Provider calls
retain those smaller bounds; an uncertain browser mutation retains its replay
key and payload. This setting is part of the built web configuration.

## Measured budgets — T44

Measured 2026-10-23/24 on the development machine (CPU only, 11.7 GB RAM shared
with a desktop session) with two public-domain Project Gutenberg texts converted
to Markdown chapters: *Strange Case of Dr Jekyll and Mr Hyde* (#43, 25.7k words,
334 passages) and *Pride and Prejudice* (#1342, 122k words, 2,101 passages).
Local models are pinned (DEC-38, DEC-41); live consolidation used Groq's free
tier (`openai/gpt-oss-120b`) on public-domain excerpts only.

| Stage | Jekyll | Pride and Prejudice |
|---|---|---|
| Parse | 0.1 s | 0.8 s |
| Local entities (GLiNER2 + fastcoref) | 228 s | 726 s |
| Appearance cues | 0.2 s | 0.8 s |
| Passage index (EmbeddingGemma) | 62 s | 215 s |
| Entities kept | 404 | 958 |
| Narrative worker peak RSS | 3.5 GB | 4.7 GB (whole measurement process) |
| Worker RSS after the job | 0.6 GB | — |
| Retrieval per query (plan, view, four paths, fusion) | 2.6 s median | about 1 s after the single-pass fix (was 32 s) |
| Lexical / vector SQL (`EXPLAIN ANALYZE`) | 39 ms / 4 ms, sequential scans | 673 ms / 19 ms, sequential scans |

Memory: before T44 a worker kept both stages' model weights for its lifetime
(2.7 GB after each job) and GLiNER2 batches of eight long passages added 2.3 GB
of padded attention, so the 130k-word novel was killed for memory twice. Each
local stage now releases its models and trims the heap; GLiNER2 runs one
passage per pass with byte-identical output. The remaining peak is fastcoref over
one chapter-aligned extraction batch, bounded by that batch's character budget,
not by book length. Run one narrative worker per 5 GB of free memory.

Queue load: one worker processes narrative jobs serially, so a novel's 16
minutes is the unit of waiting. `VISION_MAX_ACTIVE_WORKS` (default 3) bounds an
owner's queued and running works; uploads, rebuilds and retries past it answer
`429` before storing anything.

Context: with the DEC-42 budget (20 passages, 20,000 characters) every measured
selection filled the character cap. Jekyll selection recall was 27/29 gold
passages at every cap from 20,000 down to 10,000 characters and 24/29 at 8,000;
no protected evidence was dropped. One Pride query reached the 63-source
envelope limit and reported `protected_overflow` (17 sentences). Selection is
capped at 63 sources, the provider envelope's 64 less the request item.

Live consolidation on the free Groq tier: requests carrying 18,500–20,000
characters were refused outright (HTTP 413, recorded as `PROVIDER_INPUT_TOO_LARGE`)
4/4; requests with 8,100–12,700 characters (5.7k–6.6k input tokens) were accepted
3/3. The tier also allows about one consolidation a minute, so the one
immediate retry after malformed output was rate-limited both times it ran. PROP-08
records the resulting proposals; until it is accepted the DEC-42 defaults apply.

Reproduce with the opt-in harness (one book per process bounds memory; omit the
Groq key for a local-only run):

```sh
set -a; . ./.env; set +a
HF_HUB_OFFLINE=1 VISION_MEASURE_BOOKS=$PWD/.local/corpus VISION_MEASURE_ONLY=jekyll \
  VISION_TEST_ADMIN_URL=$DATABASE_URL uv run --project apps/api --locked \
  pytest apps/api/tests/test_retrieval_budgets.py -k measure_book -m integration -q
```

Results land in `.local/measurements/budgets-<book>.json`; `VISION_MEASURE_KEEP_DB`
keeps a copy of the processed database for profiling.

## Packaged local stack — T45

DEC-25 keeps Vision local, so packaging means reproducible images and a private
filesystem store rather than external hosting or S3. `make images` builds two
images from the checkout, labelled with the commit (`org.opencontainers.image.revision`):

| Image | Contents | Size (2026-10-25) |
|---|---|---|
| `vision-api:local` | Python 3.12.14 and the locked `uv` environment (CPU torch, Docling, local NLP), app and migrations; runs as uid 10001 | 5.8 GB |
| `vision-web:local` | Node 24.12.0, the frozen pnpm install and a production Next build | 1.2 GB |

Base images are pinned by digest and dependencies by lockfile. Neither image
holds `.env`, tests, private books, runtime data or model weights (`.dockerignore`).

`docker compose --profile app up -d --wait` starts PostgreSQL, Redis, a one-shot
`migrate`, the `api`, a `worker` and the `web` server:

- Only the web port is published, on `127.0.0.1:${VISION_WEB_PORT:-3000}`. The API
  listens on the stack's private network; the Next proxy reaches it as `api`, the
  one non-loopback proxy host `next.config.ts` accepts, and `VISION_TRUSTED_HOSTS`
  admits that name.
- Credentials come from the private `.env` at run time. Originals and renders live
  in the `originals` and `renders` volumes as `0700` directories with `0600` files
  owned by the service user; storage references never leave the API.
- Local models are bind-mounted read-only (`VISION_HF_HOME`, default
  `~/.cache/huggingface`, and `.local/docling-models`) with `HF_HUB_OFFLINE=1`, so no
  container downloads weights. Run `make setup` and the opt-in local-model tests once
  on the host to populate them.
- The worker first publishes pending dispatch intents, then consumes. `SIGTERM`
  lets the current message finish within a 120-second grace period; an interrupted
  narrative job is requeued by recovery within its attempt budget.
- API and web restart unless stopped; health checks use `/health/ready` and the
  web root. Logs carry request lines and safe codes only.

`make package-check` runs the built images as an isolated compose project on free
loopback ports with its own volumes, then removes it. It provisions two accounts,
uploads the synthetic story through the web proxy, waits for real ingestion and
local narrative extraction in the worker container, reads the exact original back,
checks the other account's `404` and an anonymous `401`, the volume modes, that no
`.env` or tests are baked in, that the API port is unpublished and the web server
downloads nothing at start, a graceful worker stop and an API restart. Container
logs land in `.local/package-check.log`.

## Work retention and deletion — T46

Books are retained until their owner requests deletion through the conditional
`DELETE /v1/works/{id}` API. There is no undo or automatic expiry. Acceptance
hides the book immediately; physical cleanup runs on the `retention` queue after
in-flight jobs finish. The worker removes original/image files before committing
the deletion of every work-derived database row. A minimal `work_deletions`
tombstone preserves status, ownership and replay protection without content.

The exact accepted DELETE can be replayed to inspect `pending`, `purging` or
`completed`. A stopped worker or storage error leaves cleanup unfinished; restore
storage access, then run `make dispatch` and start the worker. Repeated publication
and partially removed files are safe. This cannot recall provider-side data or
reader exports, erase disk blocks, or remove a book from an older backup.
See [security](../../SECURITY.md) for the remaining retention boundaries.

## Backup and restoration — T47

The host commands `python3 scripts/local.py backup PATH`, `deletions PATH`, and
`restore PATH --deletions LEDGER` use the selected Compose `db` service's
PostgreSQL 17 clients. `DATABASE_URL` must point into that same cluster; the
cluster identity is checked. These are offline operator commands, with the API
and worker stopped and the database left running. The tool never overwrites an
existing archive, database with user objects, or nonempty storage roots.

A snapshot is a private `0700` directory with `0600` files: a custom-format
database dump, exact original/image objects, SHA-256 manifest, schema/index
versions and the deletion ledger at that point. SQL publication is held with
table locks while copying immutable objects. The dump imports the same
[exported snapshot](https://www.postgresql.org/docs/17/app-pgdump.html) as the
reference inventory. The manifest is written and synced last. Account hashes
and private source content are included; `.env`, provider keys and model weights
are not. Encryption, off-device copies, backup frequency and expiry are
operator-managed, with no automatic schedule.

Each exported deletion ledger carries its own checksum. Restore checks it before
writing anything, so corrupted ownership/IDs cannot silently skip an erasure.
Checksums detect corruption; they do not authenticate an archive from an
untrusted source.

For the host filesystem runtime:

```sh
mkdir -p -m 700 .local/backups
python3 scripts/local.py backup "$PWD/.local/backups/before-maintenance"
# Export again after later deletions, before shutting down the source permanently.
python3 scripts/local.py deletions "$PWD/.local/backups/latest-deletions.json"
```

Create a separate empty database with `docker compose exec -T db createdb -U
vision vision_restored`. Load the private `.env` into the shell, then point
`DATABASE_URL` at that new database and `VISION_SOURCE_ROOT`/`VISION_RENDER_ROOT`
at new, empty private directories. Run:

```sh
python3 scripts/local.py restore "$PWD/.local/backups/before-maintenance" \
  --deletions "$PWD/.local/backups/latest-deletions.json"
```

For the packaged stack, stop only its application services:

```sh
docker compose --profile app stop web api worker
python3 scripts/local.py backup "$PWD/.local/backups/packaged" --packaged
python3 scripts/local.py deletions "$PWD/.local/backups/latest-packaged-deletions.json"
```

`--packaged` stages the stopped API's named volumes privately on the host. For
restoration, select a **new** `COMPOSE_PROJECT_NAME` and unused `POSTGRES_PORT`,
`REDIS_PORT` and `VISION_WEB_PORT`; point `DATABASE_URL` at the new cluster's
empty `vision` database. Start `db redis`, then create the API container without
starting migrations or application processes:

```sh
docker compose --profile app up -d --wait db redis
docker compose --profile app create --no-build api
python3 scripts/local.py restore "$PWD/.local/backups/packaged" \
  --deletions "$PWD/.local/backups/latest-packaged-deletions.json" --packaged
```

The packaged restore refuses running API/worker containers and nonempty target
volumes. It repairs the restored files to uid 10001 and `0700`/`0600`, checks
their bytes inside the actual volumes, and clears the volume's restore marker
last. The source project and its volumes remain available for rollback.

Restore uses [one database transaction](https://www.postgresql.org/docs/17/app-pgrestore.html),
revokes old sessions, applies the **latest** deletion tombstones before access
can resume, reconciles interrupted ingestion/narrative jobs, and verifies every
surviving source/image hash. Both queued and running image attempts from a
snapshot become `acceptance_unknown`: the old instance could have charged a
call after the snapshot. Neither is automatically rendered again. Replaying a
deleted work also purges its restored indexes, cache, history and model runs.

Before serving the target, choose a fresh `VISION_QUEUE_NAMESPACE`, start its
API/worker/web, run dispatch, and check readiness, two-owner original/evidence/
history reads, exports and deletion absence. The Compose app environment forwards
the namespace. Do not keep the old and restored instances processing together.

A `.restore-in-progress` marker keeps readiness, authenticated operations and
worker engine creation unavailable after an interrupted restore. Keep a failed
target offline and retry into another empty database/storage pair; do not remove
the marker to bypass failed checks. Schema or index-version mismatches are
refused before restoration: use the matching release to restore/rebuild before
upgrading, rather than silently mixing vectors or changing cited text.

The recovery point for content/accounts is the completed snapshot. Deletions
after it require the separately saved latest ledger; export and preserve that
ledger after deletions. If it is lost with the source database, an older archive
does not prove current deletion state and must not be released without
reconciliation. Accounts created after the snapshot are outside its recovery
point. Only trusted Vision archives may be restored: a database dump contains
executable SQL. These commands do not establish an off-machine disaster-recovery
target or a production RTO/RPO.

