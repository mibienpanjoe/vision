# Security and source privacy

**Status:** local authentication, owned text, PDF and EPUB uploads/library and private
source storage are implemented. Broader pipeline controls remain requirements; no
external deployment is in scope.

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

## Before external deployment

Resolve authentication, resource limits, provider data handling, retention and
deletion, backup restoration, and network exposure. Exercise unauthorized access,
prompt injection, malicious documents, and spoiler leakage tests. These are
release requirements, not reasons to describe the current repository as secure.

## Reporting

No dedicated security contact or reporting service has been configured. Contact
the repository owner privately through an established channel; do not post
credentials, private source passages, or exploit details in a public issue.
