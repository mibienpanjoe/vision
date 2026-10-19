# HTTP API contract draft

**Status:** T02 selects shared outcomes and mutation conventions (DEC-23); resource routes remain illustrative.
The health endpoints exist; resource routes below remain planned. T06 implements
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
- Effectful POSTs use a bounded opaque `Idempotency-Key` (1–128 ASCII characters
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

Before the first consuming client, define authentication, multipart/upload
encoding, collection pagination, job polling/cancellation/retry endpoints,
authorized source-span retrieval, resource-specific refinement
and deletion, streaming if needed, and version evolution. T07 owns auth, T08 job
routes, T10 upload/pagination, T12 evidence reads, T38 refinement, and T46 deletion. The overview's endpoint
list alone does not cover the complete library/evidence/job product flow.

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
