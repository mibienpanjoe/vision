# HTTP API contract draft

**Status:** shared outcomes and mutation conventions selected in DEC-23.
Health, authentication, probe jobs, private text-upload/library and bounded
evidence routes exist as detailed below; reconstruction resources remain illustrative. T06 implements
strict shared Pydantic models and generated JSON Schema/TypeScript, independently
of the illustrative resource payloads below.

## Shared requirements

Every resource is resolved within an authenticated authorized work scope.
IDs are opaque. Nested and indirect resources require the same ownership checks
as works. Model prompts, source text, secrets, and local paths never appear in
public errors. The executable Pydantic/OpenAPI contract will own serialization
and generate TypeScript types; avoid a manually duplicated frontend model.

## Resource surface

| Method and path | Intended behavior | Draft success outcome |
|---|---|---|
| `POST /v1/works` | Upload and create a work/document plus ingestion job | `202`, work and job references; upload encoding not fixed |
| `GET /v1/works` | Authorized library, ingestion summary | `200`, bounded collection; pagination not fixed |
| `GET /v1/works/{id}` | Work metadata, processing state, quality warnings | `200`, authorized work |
| `GET /v1/works/{id}/entities` | Browse in-scope entities | `200`, cutoff-filtered collection |
| `GET /v1/entities/{id}/contexts` | Available moments/appearances | `200`, admissible contextual options |
| `POST /v1/visualizations` | Resolve scope, collect evidence, reconstruct and validate | `202` if asynchronous, or explicit domain outcome; execution mode open |
| `GET /v1/visualizations/{id}` | State, specification revision, evidence, uncertainty | `200`, authorized result/state |
| `POST /v1/works/{work_id}/visualizations/{id}/renders` | Optional render of a validated revision | `202`, render job; see [image rendering](#image-rendering--t40) |

Work/entity/context queries require a reading boundary. A chapter label, ordinal,
or ID must be validated against its source revision. Whole-book and cutoff modes
must not be inferred from arbitrary client-supplied SQL filters.

## Conceptual visualization request

```json
{
  "work_id": "work-example",
  "query": "Arthur at home after the war",
  "entity_id": "entity-example",
  "story_event_id": "event-return-home",
  "source_cutoff": {"mode": "through_chapter", "chapter_id": "chapter-14"},
  "creative_mode": "canon_first",
  "style": "cinematic realism"
}
```

This fictional payload illustrates distinct subject/time/source/context concerns.
It is not a validated request schema. Resolve conflicting query and structured
fields explicitly using the selected conflict-resolution convention below.

## Result semantics

Transport acceptance, job completion, and domain resolution are separate.
A resolved result follows the [visual specification](../visualization/visual-specification.md).
`needs_context` carries admissible choices; `insufficient_evidence` explains
which information is missing. A failed attempt has a safe error and retains
its correlation reference. Do not describe an accepted job as a finished image.

Selected error envelope (executable validation follows in T06):

```json
{
  "error": {
    "code": "SOURCE_NOT_READY",
    "message": "This work is still being processed.",
    "retryable": true,
    "correlation_id": "request-example"
  }
}
```

| Condition | Selected HTTP / code |
|---|---|
| Missing authentication | `401 / AUTHENTICATION_REQUIRED` |
| Inaccessible or missing object | `404 / RESOURCE_NOT_FOUND`, avoid revealing existence |
| Invalid shape or unsupported scope | `422 / INVALID_REQUEST` |
| Work not ready or incompatible input generation | `409 / SOURCE_NOT_READY` or `GENERATION_CONFLICT` |
| Input too large | `413 / UPLOAD_TOO_LARGE` |
| Budget/rate limit | `429 / RESOURCE_LIMIT` |
| Upstream provider unavailable | `503 / PROVIDER_UNAVAILABLE` |

These shared codes/statuses are selected; resource-specific codes require their
owning task. Retryability depends on durable operation
state, not a blanket retry of every POST or provider error.

## Selected first-slice wire conventions

- Domain responses use an exhaustive `outcome` discriminator: `resolved` requires
  a validated specification; `needs_context` requires nonempty eligible choices;
  `insufficient_evidence` requires missing-information reasons; `failed` requires
  a safe error. Unknown variants are rejected. A resolved profile can retain
  unknown/disputed traits. Job states are separate and `202` carries only accepted
  operation references, never a pretend resolved result. T06 owns common types;
  T31 owns the complete specification and execution mode.
- Mutable resource responses carry a strong opaque `ETag`. Mutations require
  the exact single `If-Match` token: missing is `428 / REVISION_REQUIRED`, stale is
  `412 / REVISION_CONFLICT`. Wildcard/weak/multiple tokens are invalid requests.
  Incompatible-input generation failures use `409`; successful updates issue a new token.
  Authorization is checked before revision comparisons to avoid disclosure.
- Effectful business-operation POSTs use a bounded opaque `Idempotency-Key` (1–128 ASCII characters
  from letters, digits, `-`, `_`). Scope keys by authenticated actor, method,
  route and work; fingerprint the validated request, source upload bytes and
  referenced revisions. Same key/same request returns the existing operation;
  same key/different request gives `409 / IDEMPOTENCY_CONFLICT`. Concurrent
  submissions reserve one durable operation; network timeouts require lookup/
  reconciliation before repeating a provider effect. An in-flight replay returns
  the operation's current state. Keys remain at least 24 hours after terminal
  completion; unresolved effects retain reservations until reconciled. T10/T13
  implement the durable mechanism and communicate expiry/recovery behavior.
- Conflicting structured subject/time fields and natural-language intent return
  `needs_context` with eligible choices; do not silently override either input.
  T23 implements ambiguity resolution. Displayed choices must obey the cutoff.

Reject a stale style edit rather than overwriting a newer revision; replaying an
upload must not create a second work. A fresh key does not permit reuse of an
unauthorized work or an incompatible generation. These are selected conventions,
not claims of implemented HTTP behavior. Conditional mutation semantics follow
[RFC 9110 If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)
and [RFC 6585 precondition required](https://www.rfc-editor.org/rfc/rfc6585.html#section-3);
key syntax, scope and retention are project conventions. Creation POSTs have no
prior ETag; If-Match applies only where an existing resource revision is mutated.

## Unresolved wire details

Authentication, probe jobs, multipart uploads/library pagination, authorized
source-span retrieval and ingestion retry/cancellation are implemented below.
Before each remaining consumer, define refinement (T38), deletion (T46), and streaming/version evolution where needed.
The overview's endpoint list alone does not cover the complete
library/evidence/job product flow.

## Executable shared foundation — T06

`apps/api/app/schemas/` owns strict scope, source-span, safe-error and outcome
primitives. Extra fields, invalid tags and missing required variant payloads are
rejected. `packages/contracts/schema.json` and `index.ts` are generated from those
models; do not hand-edit them. Run:

```sh
pnpm --dir packages/contracts generate
pnpm --dir packages/contracts test
pnpm --dir packages/contracts typecheck
```

Python and Node consume the same `conformance.json` cases. The generated schema
handles structural validation; Python validators and the TypeScript source-span
helper additionally enforce code-point length, interval ordering and exact quote
matching. JSON Schema alone cannot compare two fields or query stored source text.
Ownership, actual source-revision lookup and reading eligibility are enforced at
their authoritative operation boundaries, not established by a valid scope shape.

`Resolved[Payload]` is a generic envelope with required typed `data`; the concrete
`SpanResolution` export is a conformance binding to SourceSpan, not the visual
specification or a visualization endpoint. T31 binds the actual validated visual
specification and extends generated contracts then. The build-time SchemaCatalog
is not a request payload. No speculative full visualization model is shipped.

Sources: [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-str-discriminators),
[Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/), and
[json-schema-to-typescript](https://github.com/bcherny/json-schema-to-typescript).

## Local authentication — T07

| Endpoint | Implemented behavior |
|---|---|
| `POST /v1/auth/login` | Bounded username/passphrase, generic failure, fresh opaque session, public principal view |
| `GET /v1/auth/me` | Principal resolved from a nonexpired database session; no client owner ID |
| `POST /v1/auth/logout` | Authenticated, origin-checked session revocation; `204` and cookie removal |

Accounts are provisioned only by the local administrative CLI. There is no
registration endpoint, external identity provider or development-principal
bypass. Usernames are 3–32 lowercase ASCII identifier characters; passphrases
are 12–128 code points. Passwords use versioned, randomly salted scrypt
(N=131072, r=8, p=1); only SHA-256 digests of 256-bit random session tokens are
stored. Existing browser sessions rotate on login; sessions expire after 12 hours.

The browser calls `/api/v1/*` on the Next.js origin, which forwards to the local
API. Cookie `vision_session` is host-only, HttpOnly, SameSite Strict, path `/`.
It deliberately uses HTTP on loopback without Secure under DEC-25; external
network exposure/HTTPS deployment is outside this supported configuration.
API trusted hosts are localhost/127.0.0.1. Mutations require an exact allowed
Origin (`http://127.0.0.1:3000` or `http://localhost:3000` by default). Private
`VISION_WEB_ORIGINS` can select another local test origin. No CORS grant is needed.

A fixed-memory limiter allows ten login attempts per minute per local API process,
including unknown users; it resets on process restart. Five failed passwords for
an existing account lock it for five minutes in PostgreSQL. These are initial
local protections, not a distributed rate-limit claim. Errors use the safe common
envelope and generated correlation IDs; validation does not echo input.
Authenticated responses use `Cache-Control: no-store`.

`ActorScope` comes only from the authenticated session and principal lookup.
The reusable owned-object query binds both object ID and authenticated owner,
returning the same `404` for missing/inaccessible objects. Integration tests
prove it with isolated synthetic records; T08/T10 apply it to real product jobs
and works. Client-supplied owner headers/fields never establish authority.

Verified with two real PostgreSQL-backed principals, expiry/logout, invalid
credentials/origins/fields, login limits and local CLI provisioning. An actual
Chromium navigation through the web proxy saw the authenticated principal and
then `401` after logout. This is session transport proof, not a completed login UI.

Authentication login/logout use the rotation/revocation semantics above rather
than business-operation idempotency keys; retries do not create works, jobs or
paid provider effects. This qualifies the general POST convention for sessions.

## Bounded worker probe — T08

`POST /v1/jobs` accepts an authenticated, origin-checked probe request with
`kind: "probe"` (default) and integer `value` from 0 to 1,000,000. It requires
`Idempotency-Key`. `202` returns a persisted job reference/state, not completion.
Keys are scoped by owner and this resource; same request replays the same job,
different input returns `409 / IDEMPOTENCY_CONFLICT`. Keys are retained without
expiry at this foundation stage, satisfying the minimum replay window.

`GET /v1/jobs/{id}` applies the authoritative owned-object query. Responses carry
stage, attempts, nullable result, correlation ID and `dispatch_pending`. With no
worker, published jobs remain queued; with an unreachable broker, publication
intent remains in PostgreSQL and pending stays visible. The dispatch command
reconciles unpublished jobs. Broker acceptance alone never means success.

The only implemented task increments the bounded integer. A real worker loads
the job's persisted principal/scope and writes one result/attempt under a SQL row
lock and transaction. Duplicate delivery cannot duplicate its committed result.
The instantaneous probe exposes queued/succeeded, not a simulated long-running
stage. Its attempt record retains stage, outcome and timestamps. T13 introduces
long-running ingestion stages, failures/cancellation and broader recovery.


## Private uploads and library — T10

| Endpoint | Implemented behavior |
|---|---|
| `POST /v1/works` | Authenticated multipart `title`, `format` (`txt`/`md`/`pdf`/`epub`), and one `file`; required `Idempotency-Key`; `202` with work and ingestion reference |
| `GET /v1/works` | Owner-scoped UUID-ascending keyset page; `limit` 1–100 (default 20), optional UUID `after`; `items` and nullable `next_cursor` |
| `GET /v1/works/{id}` | Owned work metadata, its first immutable document revision and `current_parser_revision` (null until a generation is published) |
| `GET /v1/works/{id}/chapters` | Current published source generation's chapter numbers and IDs, without titles; ordinal-ascending page, `after` >= 0 (default 0), `limit` 1–100 (default 100); `next_after` or null; source/generation/parser lineage retained |
| `GET /v1/works/{id}/original` | Owned original bytes as a nosniff attachment with a fixed safe filename; no public storage URL |
| `GET /v1/works/{id}/ingestions/{job_id}` | Job resolved through the owned work/document; lifecycle state, `revision` (also the `ETag`), cancel request, attempts, safe error code and structure warnings |
| `POST /v1/works/{id}/ingestions/{job_id}/retry` and `.../cancel` | Owned conditional mutation; see [ingestion recovery](#ingestion-retry-and-cancellation--t13) |
| `GET /v1/works/{id}/generations` | Owned source generations in ordinal order: parser revision, derived status, `current`, `parsed`, `narrative_ready`, `search_ready`, job ID and warnings |
| `POST /v1/works/{id}/generations` | Rebuild with the format's current parser revision; required `Idempotency-Key`, no body; `202` with the new generation |

Upload authentication and Origin checks precede body consumption. The boundary
counts actual received bytes, permits at most 64 KiB of multipart overhead,
limits fields/files and enforces the [input policy](../ingestion/ingestion-contract.md#first-upload-input-boundary--t10).
Names, MIME claims and caller-supplied ownership never establish source type,
storage path or authority. Metadata belongs in multipart fields, not URL queries;
unknown/duplicate fields and extra files fail safely. Errors use the common
safe envelope: invalid content/metadata `422`, malformed multipart `400`, size
`413`, media type `415`, transfer timeout `408`, unavailable storage `503`.

Creation keys are scoped to authenticated owner and work creation. Exact title,
format and original SHA-256 define request identity; replay returns the same
work/document/job, while changed input gives `409`. Keys currently persist with
the work without expiry. A lost acknowledgement can return `503` after SQL
committed: replay recovers the persisted reference without deleting its source.
Pagination cursors are positions, not authority; every page reapplies owner scope.
Response models are generated from `schemas/works.py`; storage references,
private filesystem paths, owner identifiers and original filenames are excluded.
The shared TypeScript catalog also exports `GenerationPage` and `GenerationView`,
including narrative status/error and separate parse, narrative and search readiness.
The chapter catalog returns `409 SOURCE_NOT_READY` until a source generation is
published, and the common owned `404` otherwise. It requires parsing, not narrative
readiness. It never returns chapter titles, source text or obsolete parser chapters.

T11 publishes text-ingestion intents through Redis to the real parser worker.
An unavailable broker leaves SQL intent visibly pending for `make dispatch`.
Successful parsing persists exact paragraph text and chapter anchors; `parsed`
does not mean the full narrative/search generation is ready.


## Authorized evidence — T12

`POST /v1/works/{work_id}/evidence` is a read-only lookup using a JSON body so
source quotes do not enter URL/access logs. It requires authentication and the
usual mutation-method Origin check, but no business idempotency key: it creates
no durable object or provider effect. The generated `EvidenceRequest` carries
a bounded `SourceSpan`, exact `parser_revision`, `reading_boundary`, and optional
`context_before`/`context_after` (0–500, default 100).

The service resolves owner → work → document revision → parser revision → passage
and chapter eligibility before validating the quote. Missing/inaccessible,
wrong-revision/parser and out-of-cutoff references return the same safe `404`.
Through-chapter mode requires an actual chapter in that exact document/parser
revision; unassigned passages fail closed. Whole-book mode permits passages with
unknown chapter structure. Quote mismatch and invalid ranges return `422`.

The response retains the validated span, parser revision, optional eligible
chapter ID, a passage-local excerpt, excerpt/highlight code-point coordinates,
original-text code-point coordinates, and nullable `pages` and `section`. For
PDF and EPUB sources the original coordinates index the parser's canonical
text. `pages` lists a PDF passage's pages. `section` gives an EPUB passage's
content document and fragment. See the
[PDF](../ingestion/ingestion-contract.md#pdf-parser-revision--t14) and
[EPUB](../ingestion/ingestion-contract.md#epub-parser-revision--t15) parser revisions. Quotes are at most 2,000 code points;
context is bounded to the same passage, with at most 3,000 returned code points.
No neighbor IDs, future chapter titles, storage paths or original filenames leak
through the response. Requests are bounded to 32 KiB of actual received JSON and
a 10-second deadline (`413`/`408`); the common error envelope never echoes quotes.
This endpoint does not render HTML or establish narrative-generation readiness.


## Ingestion retry and cancellation — T13

Both mutations require authentication, the mutation Origin check, an
`Idempotency-Key` and `If-Match` carrying the job's current strong ETag
(`"<revision>"`). The job resolves through the owned work and document, so
another owner receives the common `404`. A missing precondition returns `428`,
a stale or malformed revision `412`, and an action invalid for the current state
`409 STATE_CONFLICT`. Each response returns the job view and its new `ETag`.

Keys are scoped to one job. Replaying the same key, action and expected revision
returns the job's current view without a second effect; reusing a key for a
different action or revision returns `409 IDEMPOTENCY_CONFLICT`.

| Action | Allowed from | Effect |
|---|---|---|
| `cancel` | `queued` | Immediately confirmed `cancelled`; no worker has started it |
| `cancel` | `running` | Sets `cancel_requested`; status stays `running` until the worker or recovery confirms `cancelled` without publishing passages |
| `retry` | `failed`, `cancelled` | Returns to `queued`, clears the safe error and publishes dispatch intent; `429 ATTEMPTS_EXHAUSTED` after three attempts |

A cancel request is therefore distinct from confirmed cancellation.

A rebuild key is scoped to the document: replaying it returns that generation's
current view. A refused rebuild returns `409` with `GENERATION_IN_PROGRESS`,
`GENERATION_CURRENT` or `GENERATION_EXISTS`, as defined by the
[source generation rules](../ingestion/ingestion-contract.md#source-generations--t16). Retry and
cancel never delete or rewrite passages already published by a succeeded job.

## Narrative browse — T21

`GET /v1/works/{work_id}/entities` and
`GET /v1/works/{work_id}/entities/{entity_id}` read the latest succeeded entity,
event and fact derivations of the work's current generation. The optional
`through_chapter_id` query parameter is a chapter of that generation's parser
revision; omitting it selects the whole book. An unknown chapter, an entity not
visible at the cutoff, or another owner's work returns the common `404`. Before
an entity derivation has succeeded the routes return
`409 NARRATIVE_NOT_READY`.

Every returned record passes the
[dependency-closure rule](../narrative/narrative-contract.md#reading-boundary-implementation--t21);
spans use the `SourceSpan` contract and can be resolved through the evidence
route under the same boundary. Entity detail returns at most 200 mentions with
`mentions_truncated`. Generated types: `EntityPage`, `EntityDetail`.
`GenerationView` adds `narrative_status` (`not_started`, `queued`, `running`,
`succeeded`, `failed`) and the safe `narrative_error` code (T22).

## Visualization request resolution — T23

`VisualizationRequest` (`app/schemas/retrieval.py`) carries an optional
natural-language `query`, an optional `entity_id`, a story `moment` (`age` with
`years`, or a `phrase` such as "after the war"), a scene `context`, the
`through_chapter_id` reading boundary, `creative_mode` (`canon_first` default,
or `interpretation`) and an optional `style`. A query or an entity is required;
unknown fields are rejected. T31 exposes it on a route and generates its types.

`services/retrieval/query_plan.py` normalizes a request into a query plan with
deterministic English rules (`query-plan-v1`); the plan is internal and is not
a response body:

- **Source and story time stay separate.** "Chapter N" in the query is matched
  against the chapter's own heading number, never the parser ordinal. "Through",
  "up to", "until" and "by" narrow the reading boundary, "before chapter N" ends
  it at the preceding chapter, and "in chapter N" only focuses the source. A
  reference can narrow the boundary but never widen it: a chapter beyond the
  boundary, or one the work lacks, is `insufficient_evidence`. Ages ("at ten",
  "when he was ten", "ten years old") and before/after/during phrases become the
  story moment; at/in/on phrases become the scene context.
- **Subjects come from the cutoff-eligible narrative only.** Names are matched
  against visible mention text, display labels and aliases, with Unicode NFC
  case folding and pronouns ignored. Visible `same_as` links join identities, so
  "Wren" names Arthur only once the reveal is within the boundary. When no full
  name matches, a capitalised title word ("captain" of "Captain Mira") offers
  the identities that use it. A surface whose visible mentions point at more
  than one identity offers each one as a choice instead of picking one. Further
  named subjects are kept as scene participants.
- **Structured fields and the query text never override each other.** A
  structured entity, moment or context that disagrees with the query returns
  `needs_context` with both sides as choices (`subject` choices carry the entity
  id, `moment` and `context` choices name `request` or the query position); a
  structured entity among the query's candidates resolves the ambiguity. An
  unknown or hidden `entity_id` and another owner's work return the common
  `404`; no eligible subject is `insufficient_evidence`.
- **An unspecified moment stays unspecified.** The plan does not choose a story
  time; reconstruction (T28) must offer context choices rather than blend
  materially different states.

## Visualization compose — T31

`POST /v1/works/{work_id}/visualizations/compose` takes a `VisualizationRequest`
and returns a `VisualizationResult` with status 200 for every domain outcome:

- `resolved` with a `VisualSpecification` (`spec_version` `vision-spec-1.0`);
- `needs_context` with `choices`, each with `field` `subject` (the id is the
  entity), `moment` (resubmit the label as a `phrase` moment) or `context`;
- `insufficient_evidence` with `missing` reasons (no eligible subject, a chapter
  beyond the boundary, a moment the eligible text does not establish, no
  verified trait);
- `failed` with a safe error: `PROVIDER_NOT_ENABLED` (no `GROQ_API_KEY`),
  `PROVIDER_RATE_LIMITED`, `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE` or
  `PROVIDER_INVALID_OUTPUT` (retryable: the failed consolidation is reclaimed
  on the next request), or `PROMPT_GATE_FAILED`. Consolidation itself makes one
  more call after a malformed answer, never more. There is no fallback to
  unverified output.

Another owner's work or an unknown entity or chapter returns the common `404`,
an unauthenticated call `401`, an invalid body `422`, and a work without a
succeeded entity derivation `409 NARRATIVE_NOT_READY`. The call runs the whole
path synchronously (plan, local retrieval, Groq consolidation reused by scope,
reconstruction, verification with optional adjudication, prompt gate). It stores
only the consolidation and run records; stored results are created through
the route in the next section.
`VISION_ADJUDICATE=0` turns adjudication off.

The specification carries `lineage` (consolidation id; query-plan, consolidation,
index and parser versions), `scope` (generation, parser revision, cutoff,
requested and resolved moment, context, creative mode), the `subject`,
`participants` and `world` members (each with traits and unknown core traits),
`excluded` entities with reasons, scene `unknown`s, `creative` additions,
`generation` (style, prompt, negative prompt) and `verification` (adjudication
state, facts removed, selection outcome). Canonical and disputed traits always
carry `SourceSpan` evidence, which resolves through the evidence route under the
same boundary; inferred traits carry their reason. The negative prompt lists
only values the text rules out at this moment (removed, negated or superseded),
never a value that is merely unknown here, such as childhood hair for an adult
portrait. In `interpretation` mode,
unknown core traits of the subject become creative additions ("artist's
choice") and inferred traits enter the prompt as "possibly"; canonical traits
are identical in both modes. Generated types: `VisualizationRequest`,
`VisualizationResult` and their members. `ContextChoice` gains the optional
`field`.

## Stored visualizations — T32a

| Route | Behavior |
|---|---|
| `POST /v1/works/{work_id}/visualizations` | Requires `Idempotency-Key`. Runs compose; a `resolved` result is stored as revision 1 and returned `201` with `ETag: "1"` as `VisualizationCreated` (`visualization` and `result`). Any other outcome returns `200` with `visualization: null` and reserves nothing. The same key and request replay the stored result; the same key with a different request is `409 IDEMPOTENCY_CONFLICT`. |
| `GET /v1/works/{work_id}/visualizations` | The owner's stored visualizations of the work, newest first (at most 100), with subject label and current revision. |
| `GET /v1/works/{work_id}/visualizations/{id}` | The current revision as `VisualizationView`, with the revision as strong `ETag`. |
| `GET .../{id}/revisions` and `.../{id}/revisions/{number}` | Revision summaries (generation, parser revision, consolidation), and any stored revision. |

Keys are scoped to the owner and work and fingerprint the validated request.
Concurrent inserts under one key collapse to one stored row by a unique
constraint, and the loser replays it. Another owner's work or visualization,
or a missing revision, is the common `404`. A revision stores the full
validated result with its generation, parser revision and consolidation
(migration 0018), so its cited spans still resolve through the evidence route
after later consolidations. New revisions (refinement) arrive with T38.

T38's snapshot preparation retains each revision's own request, exact input
derivation IDs in `lineage.inputs`, and structured excluded values beside the
generation prompt. Migration 0020 backfills revision requests from the original
request and that revision's style/mode. Creation replay returns revision 1 even
after later refinement. Older specs remain readable; new cache keys (`verify-v3`)
require fresh dependency snapshots and the strengthened creative/exclusion gate.

## Presentation refinements — T38

`POST /v1/works/{work_id}/visualizations/{id}/refinements` accepts a required
nullable `style`, required `creative_mode`, and up to 32 `locks` (entity ID,
attribute and exact canonical value). It requires the current strong `If-Match`
and `Idempotency-Key`, and returns the new stored `VisualizationView` with its
revision ETag. The body/deadline share the evidence route's 32 KiB/10-second bound.

The owned visualization row serializes updates. Missing preconditions give 428,
stale/malformed revisions 412, conflicting replay 409. A durable receipt replays
the exact revision created by that key/body/expected revision, even if newer
revisions exist. Canonical/inferred/disputed profiles and evidence are copied
unchanged; style, creative additions and prompt intent are recomposed and gated.
Locks must match canonical values and survive the prompt. Creative style cannot
override a source exclusion. Unsupported locks or a failed prompt gate give safe
409 errors and publish no revision.

Source-generation or entity/appearance/index changes require a new reconstruction
(409 `SCOPE_CHANGED`/`DEPENDENCIES_CHANGED`). Subject, moment and boundary are not
mutation fields; changing them uses compose and revalidation. Every citation is
re-resolved under the stored scope before publication. No provider call is needed
for this presentation-only mutation. Older specifications without dependency
snapshots remain readable but require a new reconstruction before refinement.
Migration 0021 adds receipts; downgrading it discards receipts while retaining
immutable revision results. Migration 0020 can reconstruct their style/mode
requests from those results on a subsequent upgrade.
Generated types: `VisualizationCreated`, `VisualizationView`,
`VisualizationPage`, `RevisionPage`.

History list/read/revision endpoints accept optional `generation_id` and
`through_chapter_id` filters. The browser always supplies the current generation;
with that filter, omitting the chapter means exact whole-book scope. The generation
must be the work's current published generation, and the chapter must belong to
it. Lists include only exact scope matches, and incompatible reads/revision lists
return the common 404. Omitting both filters retains the existing owner-authorized
archive API; it is not used by a chapter-limited browser view.

## Image rendering — T40

Rendering follows DEC-51 (D5). It is off unless the private environment sets
`VISION_RENDER_PROVIDER` and that provider's key; otherwise a new reservation
returns `503 RENDER_NOT_CONFIGURED`. `openai` (`OPENAI_API_KEY`) selects
`gpt-image-1` at low quality, PNG; `huggingface` (`HF_TOKEN`) selects
`black-forest-labs/FLUX.1-schnell` through the Hugging Face router's `nscale`
route. Both render 1024×1024. Each reservation records its provider/model and
allows at most one charged provider call.

| Route | Behavior |
|---|---|
| `POST /v1/works/{work_id}/visualizations/{id}/renders` | Body contains only positive integer `specification_revision`; `Idempotency-Key` required. Returns `202 RenderView` for a durable reservation, or `503 RENDER_NOT_CONFIGURED`. |
| `GET /v1/works/{work_id}/renders/{id}` | Owner-authorized `RenderView` with strong revision ETag; wrong owner/work returns safe 404. |
| `POST /v1/works/{work_id}/renders/{id}/cancel` | Empty JSON object, `If-Match` and `Idempotency-Key`; returns the saved cancellation receipt and ETag. |

A new reservation locks the visualization head and source pointer, requires the
current specification revision and exact source/derivation inputs, and retains
the entire immutable specification plus its SHA-256 and provider/model identity.
Raw prompts and arbitrary provider settings are rejected. Request keys are scoped
to owner and visualization: the same request returns that reservation's current
state, while changed input returns 409. Replay precedes current configuration and
dependency checks, so it cannot reserve a second call after configuration changes.

Reservations are serialized per owner and capped at five, counting every
reservation whatever its outcome (`429 RENDER_LIMIT`). A retry after any outcome
is a new, explicit, counted reservation; there is no automatic retry and no
reconciliation route, because the provider exposes neither request lookup nor
idempotency keys.

After commit the reservation is published to the `render` queue; `dispatched:
false` means publication has not occurred and `make dispatch` retries it. The
worker claims a queued job (`running`, revision +1), sends only the snapshot's
`generation.prompt`, and settles atomically with a terminal revision:

| Status / `error_code` | Meaning |
|---|---|
| `succeeded` | Image bytes verified as PNG/JPEG/WebP (≤ 16 MiB) and stored privately; `output_sha256` and `output_media_type` describe them |
| `failed` `PROVIDER_UNAUTHORIZED` / `PROVIDER_QUOTA_EXCEEDED` / `PROVIDER_RATE_LIMITED` / `PROVIDER_CONTENT_REFUSED` / `PROVIDER_REJECTED` | The provider answered with an HTTP refusal (401/403; 402 or an exhausted-quota code; 429; a moderation block; other) and returned no image; provider messages are discarded |
| `failed` `PROVIDER_UNAVAILABLE` | The connection was refused or the name did not resolve; nothing was sent |
| `failed` `PROVIDER_INVALID_OUTPUT` | The provider answered 200 but returned no verifiable image; the call may have been charged |
| `failed` `RENDER_STORAGE_FAILED` | The provider returned an image that could not be stored; the call was charged |
| `failed` `RENDER_NOT_CONFIGURED` | Rendering was disabled, or the configured model differs from the reserved one, when the worker ran; nothing was sent |
| `acceptance_unknown` `PROVIDER_ACCEPTANCE_UNKNOWN` | The request may have been sent but no response arrived (timeout of 120 s, reset); it may have been charged |
| `acceptance_unknown` `RENDER_INTERRUPTED` | A claimed job was redelivered or found running by `make dispatch` with no worker holding it |

A claimed job is never sent again: the actor has no retries, and a redelivered
`running` job settles as `acceptance_unknown` without calling the provider.

Queued cancellation becomes cancelled immediately and the worker then skips it.
Cancelling a running job records `cancel_requested` and keeps it running; the
in-flight call is not interrupted and its outcome, including a stored image, is
kept. Missing/stale preconditions return 428/412; reusing a cancellation key with
another expected revision returns 409. Exact cancellation replay returns the
captured response even if later state changes. No cancellation or timeout claims
that an external charge was reversed.

The image's lineage is the reserved specification revision and hash, provider,
model, recorded settings (size, quality or route, `negative_prompt: not_sent`,
prompt SHA-256) and any provider-reported token usage. The private storage reference is never returned. Viewing or
downloading the image belongs to T41; generated pixels never become evidence.
