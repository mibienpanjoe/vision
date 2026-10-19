# Ingestion and source-mapping contract

**Status:** baseline behavior plus marked implementation proposals.
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

Use zero-based, end-exclusive **Unicode code-point** offsets against immutable
stored passage text: `[start, end)`, with `0 <= start < end <= length(text)`.
Passages retain mapping to parser blocks/original pages where available; do not
claim normalized offsets are original PDF byte offsets.

Example: `Arthur wore a blue coat.` has `blue coat` at `[14, 23)`. Validate
the quoted text against the actual slice. Python and browser JavaScript must
agree on code points; JavaScript UTF-16 offsets need an explicit conversion,
especially for emoji and supplementary characters. Test Unicode normalization,
accents, paragraph breaks, and negation windows before fixing this proposal.

Changing text normalization creates a new text/parser revision. Do not reuse a
passage ID for changed text or let old spans point into new content. Stable IDs
mean old references remain meaningful; they do not promise identical IDs after
arbitrary resegmentation.

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

Build a named new generation from the original revision. Publish it only after
reference and compatibility checks; keep an earlier usable generation available
where policy permits. Namespace embeddings by model/dimension/version and states
by their input generation. Invalidate dependent states when extraction changes.
Cross-system index publication needs an explicit durable recovery design.

## Failure categories and safeguards

Invalid or oversized input fails before expensive work. Unsupported formats,
encrypted/unreadable files, parser failures, missing structure, ambiguous
extraction, provider outages, budget exhaustion, and cancellation produce
distinct safe outcomes. Do not leak paths or source text in errors.

Resource ceilings and retry policy are configurable but not numerically chosen.
Follow [SECURITY.md](../../SECURITY.md) for untrusted content, EPUB expansion,
private storage, and provider disclosure. Operations and restoration procedures
belong to [development and operations](../operations/development-and-operations.md).
