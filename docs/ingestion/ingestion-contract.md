# Ingestion and source-mapping contract

**Status:** first-slice source/generation semantics selected by T02; job wire details remain draft.
**Scope:** upload through a usable derived index; no parser or worker exists yet.

## Input and output

Input is an authorized work, a private source object, detected format, and
processing configuration. The baseline formats are PDF, EPUB, TXT, and Markdown.
Docling and format-specific adapters produce a common representation; exact
parser coverage, OCR, and runtime versions remain OPEN-06.

Successful output contains the document revision, ordered sections/passages,
exact anchors, parser/segmentation metadata, quality warnings, entity mentions,
events and visual claims with provenance, and compatible searchable indexes.
Scene detection may be uncertain; passages remain usable when no scene can be
reliably identified. Missing structure is not silently invented.

## Processing stages

```text
Validate and retain original
  → parse and map source locations
  → segment paragraphs and retrieval windows
  → extract/link entities, events and visual claims
  → build lexical and semantic indexes
  → validate references and quality
  → publish compatible generation or report failure/degradation
```

Durable progress records stage and outcome. API acceptance is not completion.
Model extraction results are validated before becoming eligible narrative data.
The worker delegates domain logic to services rather than implementing a second
extraction pipeline inside job handlers.

## Source span proposal — PROP-01

**Selected:** DEC-20 supersedes the proposal; heading retained for existing links.

Use zero-based, end-exclusive **Unicode code-point** offsets against immutable
stored passage text: `[start, end)`, with `0 <= start < end <= length(text)`.
Passages retain mapping to parser blocks/original pages where available; do not
claim normalized offsets are original PDF byte offsets.

Example: `Arthur wore a blue coat.` has `blue coat` at `[14, 23)`. Validate
the quoted text against the actual slice. Python and browser JavaScript must
agree on code points; JavaScript UTF-16 offsets need an explicit conversion,
especially for emoji and supplementary characters. Test Unicode normalization,
accents, paragraph breaks, and negation windows in executable contract tests.

Changing text normalization creates a new text/parser revision. Do not reuse a
passage ID for changed text or let old spans point into new content. Stable IDs
mean old references remain meaningful; they do not promise identical IDs after
arbitrary resegmentation.

The stored passage is the offset authority: retain its exact code points, with
no client-side NFC/NFD conversion, trimming or newline replacement. Normalize
only when producing a new immutable parser revision. A quote mismatch, empty
span, byte offset, UTF-16 surrogate boundary or out-of-range value is invalid.
For `é🦊é`, `[1,2)` is `🦊` and `[2,4)` is the decomposed `é`; its total length
is four code points, five UTF-16 units and nine UTF-8 bytes. A reader must map
code points to UTF-16 only for DOM highlighting. T03 checks Python slices;
T06/T36 prove executable client conversion and highlighting.

## Job lifecycle proposal

Use explicit queued/running/succeeded/failed/cancelled states with stage and
safe error details. If partial parsing is usable, expose the coverage and
warnings distinctly; “succeeded” must not imply full coverage unless established.
The exact degraded-result representation is settled with the executable schema.

Persist attempts, configuration versions, document fingerprint, and durable
outputs. A retry must not duplicate facts or advertise a half-built index as
current. Propagate cancellation into bounded stages; confirm terminal state
rather than immediately treating a cancel request as completion. The initial
API routes for retry and cancellation are still draft additions.

## Reprocessing proposal — PROP-02

**Selected:** DEC-21 supersedes the proposal; heading retained for existing links.

Build a named new generation from the original revision. Publish it only after
reference and compatibility checks; keep an earlier usable generation available
where policy permits. Namespace embeddings by model/dimension/version and states
by their input generation. Invalidate dependent states when extraction changes.
Separate source availability, narrative eligibility and search eligibility.
Publication uses an atomic PostgreSQL pointer update conditional on the expected
previous generation, after validating immutable document/parser/extraction and,
where required, embedding/retrieval dependencies. Candidate/failed generations
cannot satisfy readiness; a late-finishing older rebuild cannot overwrite the
selected newer result. Old cited passages remain addressable by their original
revision under ownership and retention policy. T16/T22/T25 implement the stages;
no cross-system atomic transaction is assumed. A compatible partial parser result
must expose its warnings and coverage; it cannot imply whole-document coverage.

## Failure categories and safeguards

Invalid or oversized input fails before expensive work. Unsupported formats,
encrypted/unreadable files, parser failures, missing structure, ambiguous
extraction, provider outages, budget exhaustion, and cancellation produce
distinct safe outcomes. Do not leak paths or source text in errors.

Resource ceilings and retry policy are configurable but not numerically chosen.
Follow [SECURITY.md](../../SECURITY.md) for untrusted content, EPUB expansion,
private storage, and provider disclosure. Operations and restoration procedures
belong to [development and operations](../operations/development-and-operations.md).


## First upload input boundary — T10

The first upload slice accepts UTF-8 TXT and Markdown, retaining the exact bytes
without Unicode or newline normalization. Empty text, invalid UTF-8, binary
control characters and obvious PDF/ZIP disguises are rejected. PDF and EPUB
acceptance follows the dedicated format-adapter tasks; a text upload does not
establish parser or narrative success.

Initial limits are 8 MiB per source, a 60-second transfer deadline, titles up to
256 code points and library pages up to 100 records. These are conservative
engineering ceilings under OPEN-05, not measured whole-book capacity claims.
Parser expansion/time and provider budgets are resolved at their consumers.

Originals live under ignored `storage/originals/` (or a private
`VISION_SOURCE_ROOT`) using random opaque references, directory mode 0700 and
file mode 0600. Original names and paths never form storage keys or public URLs.
File leases protect in-flight writes from reconciliation; fsync precedes SQL
publication. The upload/library API and interrupted-upload reconciliation are
the next T10 increment.
