# Security and source privacy

**Status:** local authentication, owned uploads in four formats, private source and
image storage, scoped narrative, reconstruction and rendering are implemented and
covered by the cross-boundary regression below. No external deployment is in scope.

## Trust boundaries

An uploaded book is untrusted data. Its contents cannot override system prompts,
request tools, select credentials, execute code, or alter authorization. Parsers,
model output, generated JSON, and user-supplied Markdown/HTML require validation
at their respective boundaries.

Every work and derived object is private to its authorized owner by default.
Authorization applies to library results, jobs, passages, entities, indexes,
cached states, visualization history, downloads, and image assets. A work ID is
not permission to read it. Local CLI-provisioned sessions and authoritative ActorScope are selected in
[DEC-26](docs/product/decision-register.md).

## Uploads and evidence

- Validate allowed formats and actual content; do not trust filename or MIME alone.
- Bound file size, decompression, parser time, extracted text, and model usage.
  EPUB is a container: reject unsafe paths and oversized expanded contents
  before parsing, refuse XML entity declarations and never load book resources.
- Parse PDFs only in the worker, offline from a local model directory, with
  encryption, page-count and document-time limits checked; no embedded link,
  remote service or OCR model is used.
- Store originals outside public web roots under opaque storage references.
- Escape document text in the reader and evidence inspector.
- Return only authorized, bounded excerpts. Avoid public exposure of full books.
- Do not place private books, embeddings, prompts containing source text, or
  generated runtime outputs in Git or public logs.

## Providers and operations

Provider calls may transmit source excerpts outside the deployment. Provider
selection must record data handling, retention, cost, and necessary user-facing
disclosure before live use. Provider adapters have scoped credentials; the web
client never receives provider secrets.

Keep credentials in environment or secret storage, not documentation, committed
configuration, URLs, screenshots, model prompts, or logs. Telemetry uses IDs,
versions, safe error codes, durations, and usage totals. Source text and full
provider responses are excluded by default.

Optional image rendering (DEC-51) sends only a specification's composed prompt to
the selected provider: OpenAI, whose API may retain it for abuse monitoring
(about 30 days without zero data retention), or Hugging Face's router and its
`nscale` provider. Their retention follows their terms and is not verified as
zero-retention. Rendered images are stored
privately next to originals and their storage references are never returned.

Reading boundaries apply before provider calls and cache access, as well as at
response time. A fact whose visible evidence is in scope can still leak a later
resolution if its derived dependencies are out of scope.

## Cross-boundary regression

These suites run against real PostgreSQL, Redis, workers and a browser; they
prove the local system, not a deployment:

- `apps/api/tests/test_security_boundaries.py` enumerates every generated API
  operation. Absent and logged-out sessions get `401`; a foreign or missing
  `Origin` gets `403` on every mutation; another owner's identifiers, and nested
  identifiers under another work, answer exactly like unknown ones; a cutoff
  naming another work's chapter is refused; refused calls change no stored row;
  owner responses never carry storage references, paths or secrets; every JSON
  body is capped at 32 KiB before it is read.
- `apps/api/tests/test_hostile_documents.py` uploads markup, prompt injection,
  invisible controls and a traversal filename: the bytes and passages stay exact
  and inert under an opaque name, the download name is fixed, and a NUL byte is
  refused before any source exists. A reader's own words reach a model only in
  the data block, and asking for text past the cutoff fails before any call. A
  model that obeys an injection cannot place invented, later-chapter or unquoted
  claims in a specification, and extra fields such as grants or tools fail the
  output schema. Logs and error bodies carry no source text, quotes or passwords.
- `apps/web/tests/security.spec.ts` renders hostile titles and markup without
  running them, shows another reader a not-found page and `404`s, makes stale
  controls in a second tab fail once the first signs out, and checks framing and
  proxy origin headers. The browser harness then scans the API and worker logs
  for source text and passwords.

Book-borne injection is held at the provider envelope: system instructions are
fixed, source text is quoted data, and outputs are schema-validated and grounded
against the passages (`test_provider_contracts.py`). Parser bounds for EPUB
containers, PDF limits and upload size live with their format tests.

## Before external deployment

Work deletion (DEC-52) immediately removes access and queues irreversible cleanup.
The retention worker waits for in-flight jobs and removes originals, generated
images and all work-derived rows, retaining only a minimal replay/lifecycle
tombstone. Interrupted cleanup is recovered by `make dispatch`. This removes
application references and files; it is not secure erasure of disk blocks or a
promise to recall provider-side data, exported downloads or existing backups.
Provider-side image deletion/retention remains unverified. There is no automatic
time-based retention. Account deletion is a separate local-administration
follow-up; it is not implemented by deleting a book.

Restoration requires an empty target and the latest separately saved deletion
ledger. Its checksum is checked before any restore writes, detecting corruption
that could otherwise silently skip a deletion. Restore revokes old sessions, purges deleted content before serving, and
refuses incompatible schema/index state. An interrupted restore leaves a marker
that blocks API access/readiness and worker engine creation. Queued or running
image attempts in a backup are treated as acceptance unknown, avoiding an
automatic repeat of a call charged after that backup. Snapshots contain private
content and account hashes; they are owner-only, but encryption and expiry are
operator-managed. A lost latest ledger prevents claiming that an older backup
preserves subsequent deletion choices. See the
[restoration procedure](docs/operations/development-and-operations.md#backup-and-restoration--t47).

Resolve authentication, resource limits, provider data handling, retention and
deletion, backup restoration, and network exposure. Exercise unauthorized access,
prompt injection, malicious documents, and spoiler leakage tests. These are
release requirements, not reasons to describe the current repository as secure.

## Reporting

No dedicated security contact or reporting service has been configured. Contact
the repository owner privately through an established channel; do not post
credentials, private source passages, or exploit details in a public issue.
