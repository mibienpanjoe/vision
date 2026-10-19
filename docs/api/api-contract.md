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
| `POST /v1/visualizations/{id}/render` | Optional render of a validated revision | `202`, render-job reference; later milestone |

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

Authentication, probe jobs and multipart uploads/library pagination are
implemented below. Before each remaining consumer, define authorized source-span
retrieval (T12), ingestion retry/cancellation (T13),
refinement (T38), deletion (T46), and streaming/version evolution where needed.
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
| `POST /v1/works` | Authenticated multipart `title`, `format` (`txt`/`md`), and one `file`; required `Idempotency-Key`; `202` with work and ingestion reference |
| `GET /v1/works` | Owner-scoped UUID-ascending keyset page; `limit` 1–100 (default 20), optional UUID `after`; `items` and nullable `next_cursor` |
| `GET /v1/works/{id}` | Owned work metadata and its first immutable document revision |
| `GET /v1/works/{id}/original` | Owned original bytes as a nosniff attachment with a fixed safe filename; no public storage URL |
| `GET /v1/works/{id}/ingestions/{job_id}` | Job resolved through the owned work/document; queued or terminal parser state, attempts, safe error code and structure warnings |

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
chapter ID, a passage-local excerpt, excerpt/highlight code-point coordinates
and original-text code-point coordinates. Quotes are at most 2,000 code points;
context is bounded to the same passage, with at most 3,000 returned code points.
No neighbor IDs, future chapter titles, storage paths or original filenames leak
through the response. Requests are bounded to 32 KiB of actual received JSON and
a 10-second deadline (`413`/`408`); the common error envelope never echoes quotes.
This endpoint does not render HTML or establish narrative-generation readiness.
