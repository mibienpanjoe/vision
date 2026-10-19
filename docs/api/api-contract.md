# HTTP API contract draft

**Status:** illustrative resources from overview §8, expanded as PROP-03.
There are no implemented endpoints or generated OpenAPI schemas yet. Do not
build clients against these shapes as if they were frozen.

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
fields explicitly; precedence is an implementation decision, not a silent guess.

## Result semantics

Transport acceptance, job completion, and domain resolution are separate.
A resolved result follows the [visual specification](../visualization/visual-specification.md).
`needs_context` carries admissible choices; `insufficient_evidence` explains
which information is missing. A failed attempt has a safe error and retains
its correlation reference. Do not describe an accepted job as a finished image.

Proposed error envelope:

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

| Condition | Proposed HTTP / code |
|---|---|
| Missing authentication | `401 / AUTHENTICATION_REQUIRED` |
| Inaccessible or missing object | `404 / RESOURCE_NOT_FOUND`, avoid revealing existence |
| Invalid shape or unsupported scope | `422 / INVALID_REQUEST` |
| Work not ready or incompatible revision | `409 / SOURCE_NOT_READY` or `REVISION_CONFLICT` |
| Input too large | `413 / UPLOAD_TOO_LARGE` |
| Budget/rate limit | `429 / RESOURCE_LIMIT` |
| Upstream provider unavailable | `503 / PROVIDER_UNAVAILABLE` |

Exact codes and statuses are proposals. Retryability depends on durable operation
state, not a blanket retry of every POST or provider error.

## Unresolved wire details

Before the first consuming client, define authentication, multipart/upload
encoding, collection pagination, job polling/cancellation/retry endpoints,
authorized source-span retrieval, idempotency and revision tokens, refinement
and deletion, streaming if needed, and version evolution. The overview's endpoint
list alone does not cover the complete library/evidence/job product flow.
