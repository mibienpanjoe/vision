# Agent guide

Instructions for coding agents working in this repository. Human contributors
follow [CONTRIBUTING.md](CONTRIBUTING.md); this file adds the operational detail
an agent needs and does not override it.

## What Vision is

Vision turns privately uploaded books into source-grounded, spoiler-safe visual
specifications. Every claim must trace to an exact source span within the
reader's allowed scope. Start with the
[documentation map](docs/documentation-map.md); the owning specification for an
area outranks summaries, and an accepted design is not an implemented capability.

## Repository layout

| Path | Contents |
|---|---|
| `apps/api/` | FastAPI modular monolith, SQLAlchemy models, Alembic migrations, Dramatiq workers, pytest suite |
| `apps/api/app/api/v1/` | HTTP routes; thin, delegating to `services/` |
| `apps/api/app/services/` | Domain logic: `ingestion/` (upload, parse, jobs, adapters), `verification/`, dispatch |
| `apps/api/app/schemas/` | Pydantic contract models; source of generated TypeScript types |
| `apps/api/app/workers/` | Dramatiq actors (`bootstrap.py`) and the dispatch/reconcile entry point |
| `apps/web/` | Next.js shell; read `apps/web/AGENTS.md` before changing it |
| `packages/contracts/` | Generated `schema.json`/`index.ts` plus Node conformance tests |
| `docs/` | Owning specifications, decision register, ADRs |
| `scripts/` | `local.py` command runner, documentation checker, browser session check |

## Commands

The [operations guide](docs/operations/development-and-operations.md) owns
setup and verification. Common targets:

```sh
make setup services migrate   # first run: deps, PostgreSQL/Redis, migrations
make lint unit                # Ruff and non-integration pytest
make integration              # real PostgreSQL/Redis/worker tests
make contracts                # regenerate types; fails on uncommitted drift
make web-check docs           # web build/type/browser shell, docs checker
make check                    # lint unit contracts web-check docs
```

Run a single integration file with the private `.env` loaded:

```sh
set -a; . ./.env; set +a
VISION_TEST_ADMIN_URL=$DATABASE_URL VISION_TEST_REDIS_URL=$REDIS_URL \
  uv run --project apps/api --locked pytest apps/api/tests/<file>.py -m integration -q
```

`make contracts` exits non-zero when a schema change regenerated the files;
review and commit the regenerated `packages/contracts` output with the change.

## Code conventions

- Match surrounding code: compact functions, sparse comments that explain
  *why*, no speculative abstractions. Ruff config lives in `ruff.toml`.
- Every owned resource resolves through `owned_object` or an owner-joined query;
  another owner's resource returns the common safe `404`, never `403`.
- Errors leave through `PublicError` with a stable code and safe message; never
  echo quotes, paths, filenames or owner identifiers.
- Mutations of existing resources require `If-Match` with the strong revision
  ETag and an `Idempotency-Key`; creation requires only the key.
- Durable work records SQL intent before broker publication; a failed enqueue
  stays visibly pending for `make dispatch`. Workers must be idempotent under
  redelivery and publish outputs atomically with their terminal state.
- Source text is immutable per parser revision. Spans are Unicode code points;
  never rewrite text underneath an existing citation.
- Schema changes need an Alembic migration with a working downgrade.

## Verification standard

Report the evidence level actually reached. Mocks prove simulated results only;
integration claims need real PostgreSQL, Redis and worker behavior, and a
cross-boundary feature needs a browser check. Follow test-first where practical
and never mark work done on a queued or skipped run. The
[acceptance strategy](docs/testing/acceptance-strategy.md) defines each level.

## Workflow

- One branch and pull request per phase (`phase/NN-name`); one commit per
  verified task, subject prefixed with the task ID, e.g. `feat: T13 ...`.
- Update the owning specification, API contract and decision register in the
  same commit as the behavior they describe.
- `tasks/` holds the local plan and checklist: read it for task scope and record
  evidence there, but never stage, commit or force-add it. Keep `.local/`,
  `.env`, private books and runtime data out of commits too.
- Do not merge, rewrite published history or change accepted decisions without
  the maintainer's instruction; record missing choices as proposals.

## Code exploration

A Codebase Memory index of this repository exists (`codebase-memory-mcp`).
Prefer its graph search and call tracing over broad text search, and refresh it
after each committed change because it does not watch this project:

```sh
codebase-memory-mcp cli --quiet index_repository --repo_path "$PWD"
```
