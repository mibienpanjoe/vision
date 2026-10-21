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

### Lexical and entity-linked retrieval — T24

`passages.search` is a stored `to_tsvector('english', text)` column with a GIN
index (migration 0015); English is the only configured language (DEC-22).
`services/retrieval/lexical.py` produces three candidate paths for one query
plan, each restricted in SQL to the plan's document, parser revision and reading
boundary before rows are returned:

- `entity`: whole passages with a mention resolved to the subject's visible
  identity group, most mentions first, carrying the exact mention spans.
  Mentions that only list the subject as a candidate are not linked.
- `appearance`: description sentences from the appearance derivation whose
  resolved mentions include the subject. These are **protected**: later ranking
  may reorder them but may not drop them for a low similarity score.
- `lexical`: passages matching any name phrase (`phraseto_tsquery`, so word
  order counts) or request term (`plainto_tsquery` of the moment and context),
  ordered by how many distinct names and terms match, then cover density.
  Names are the visible surfaces that identify only this subject at the cutoff,
  so a shared title such as "captain" never widens the search.

`services/retrieval/evidence.py` merges candidates by exact passage span, keeps
each path's rank, protection and anchors, and renders `SourceSpan` quotes from
the immutable passage text.

### Semantic indexing and retrieval — T25

The local `index` stage (`services/retrieval/semantic.py`) embeds every passage
of a generation with EmbeddingGemma-300M at the pinned revision `57c266a7`,
fp32 on CPU, with the model's `document` prompt and a 512-token window, and
stores 768-dimension vectors in `passage_embeddings` (migration 0016, pgvector)
under one derivation. Its processing version names the weights, revision,
precision, window, sentence-transformers and torch versions and the dimension,
so a model change adds a new derivation, and a query is answered only from the
derivation built by the same embedder version; vectors never mix. A different
dimension is refused. Local narrative jobs run `entities → appearance → index`;
the index success sets `search_ready_at`.

Queries embed appearance-oriented expansions of the subject's visible label (per
entity kind) plus the requested moment and context with the `query` prompt, and
order passages by their smallest cosine distance to any expansion. Passages are
restricted to the plan's document, parser revision and boundary in SQL, and are
not filtered by entity, so descriptions that never name the subject remain
reachable. Scans are exact; an ANN index waits for measurements (OPEN-06).
`HashedEmbeddings` is a deterministic stand-in for tests of scope and versioning.
The reader's own query text is the first expansion.

### Fusion and protected selection — T26

`services/retrieval/fusion.py` merges candidates per passage, keeping each
path's best rank, the protected sentence spans and the subject anchors, and
orders passages by weighted reciprocal rank (k = 60): semantic 1.0, lexical
0.5, entity and appearance 0. The entity and appearance paths still supply
anchors and protection; giving them rank weight lowered recall@5 without
raising selection recall.

Selection fills a budget of 20 whole passages and 20,000 characters (about
5,000 tokens, ADR-0003). Protected sentences are reserved first, as sentences,
so a low similarity score never drops them; a protected passage is sent whole
only when its rank earns a slot. Whole passages are then taken first for any
visual category (body, attire, colour and material, structure, light) not yet
covered within the top 40, then by rank. Near-duplicate passages (same words)
are sent once. The selection reports `complete`, `compressed` (protected
passages sent as sentences only), `truncated` (lower-ranked unprotected
passages left out, with the count) or `protected_overflow` (protected sentences
alone exceed the budget, with the count); it never drops protected evidence
silently.

Measured on *Jekyll and Hyde* through the real local pipeline (334 passages,
21 of the 25 research queries resolved to a subject; the other four asked for
context), recall of the gold passages:

| Ordering | @5 | @10 | @20 | Budgeted selection |
|---|---|---|---|---|
| Semantic only | 0.70 | 0.84 | 0.92 | 0.79 (old rule) |
| Lexical only | 0.49 | 0.59 | 0.71 | 0.62 (old rule) |
| Equal-weight RRF | 0.49 | 0.63 | 0.88 | 0.74 (old rule) |
| **Semantic 1.0 + lexical 0.5** | **0.74** | 0.82 | **0.93** | **0.93** |

The old rule took whole protected passages first and capped selection recall
at 0.79 whatever the weights. One novel and 21 queries cannot fix a target
(OPEN-05); the opt-in harness is `tests/test_retrieval_measurement.py`.

### Context expansion and the Groq adapter — T27

`services/retrieval/rerank.py` adds, for a selected passage that never names
the subject or whose protected sentence opens with a pronoun, the passage just
before it as attribution context, inside the same budget. Only earlier
passages of the visible narrative are added, so expansion cannot cross the
reading boundary; a refusal for budget is counted (`unexpanded`). No reranking
model is used: weighted fusion already reaches 0.93 selection recall on Jekyll
(DEC-42), and a MiniLM reranker remains an unmeasured option.

`GroqGateway` (`app/providers/openai_compatible.py`, DEC-36) sends
`openai/gpt-oss-120b` requests with `json_schema` guidance (`strict: false`;
the envelope still validates strictly) and `reasoning_effort: low`, because
gpt-oss reasoning counts against the output budget. It reads `GROQ_API_KEY` and is disabled
without it. Both chat adapters honour a 429 `retry-after` once when the wait is
at most 20 seconds and fits the call's time bound; otherwise the call ends as
`rate_limited` instead of retrying immediately. Consolidation uses bounds of
90 s, 24,000 input characters, 4,096 output and 12,000 total tokens.

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
`budget_exhausted`, `cancelled`, `provider_unavailable`, `input_too_large` or
(T27) `rate_limited` (`PROVIDER_RATE_LIMITED`).
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
Under DEC-37 this ingestion-time LLM path is limited to synthetic fixtures;
[ADR-0003](../adr/0003-local-ingestion-minimal-disclosure.md) moves private-book
extraction to local models and consolidation to query time.
A second live run of the full entity → event → fact chain succeeded on the
synthetic corpus (bounded retries absorbed three unavailable routes and two
invalid outputs). Review: rumor, metaphor and dream claims stayed
non-canonical, the sword stayed Brann's, the childhood memory kept its
modality, and the war scar was attributed correctly. Gaps: seven facts were
rejected because their subject did not match an entity label exactly (most of
the house roof history was lost), one of the two conflicting eye colours was
not extracted so no conflict was recorded, attribute names varied
(`left_cheek` vs `left_cheek_scar`), and one entity split recurred ("Captain
Brann" / "Brann"). Live quality is therefore partial and not a release claim.

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
