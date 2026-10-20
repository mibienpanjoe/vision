# Ingestion and source-mapping contract

**Status:** private TXT/Markdown upload and library boundary implemented;
source/generation semantics selected by T02.
**Scope:** the text worker persists source-linked chapters and passages. Narrative
indexing, richer format adapters and broader ingestion recovery remain pending.

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
rather than immediately treating a cancel request as completion. T13 implements
this lifecycle for text parsing; see [ingestion recovery](#ingestion-recovery--t13).

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

Initial upload ceilings are selected below; parser/provider limits and retry
policy are settled at their respective consumers.
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
publication. One transaction publishes the work, immutable document revision and
queued ingestion intent. A failed write or rolled-back flush discards its file.
An uncertain COMMIT keeps the file because SQL may already reference it. The
reconciliation command removes only unreferenced originals older than one hour
after acquiring a nonblocking exclusive lease; linked or active files survive.
A database failure prevents cleanup rather than guessing source availability.

Ingestion jobs are separate from the harmless T08 probe jobs. A text worker
loads only the persisted job/source references, verifies the original SHA-256
and persists versioned chapters/passages plus a parsed outcome in one locked SQL
transaction. Redelivery of a terminal job is harmless. Public job states are
queued, succeeded/parsed or failed with a safe code, attempt count and structure
warnings. Parsed means source paragraphs are available, not narrative/index
readiness. T13 adds retry/cancellation and interrupted-stage recovery below.

## Ingestion recovery — T13

Text jobs move through `queued` → `running` (stage `parse`) → `succeeded`/
`parsed`, `failed` or `cancelled`. Each job carries a monotonically increasing
`revision` for conditional mutations; the
[API contract](../api/api-contract.md#ingestion-retry-and-cancellation--t13)
owns the wire behavior.

A worker first takes a PostgreSQL session advisory lock on a dedicated
connection, so concurrent deliveries of one job never run together and a killed
worker's lease ends with its connection. Under that lease it claims the job in a
short transaction, increments `attempts` and records a running
`ingestion_attempts` row. Reading and parsing happen outside any SQL
transaction. A second locked transaction then either confirms a requested
cancellation, records a safe failure code, or publishes every chapter and passage
together with the succeeded outcome. Partial output is never visible, and
redelivery of a terminal job is harmless.

A worker that finds its job still `running` treats the previous attempt as
`abandoned` (or `cancelled` when requested) before continuing. `make dispatch`
and `make worker` first reconcile interrupted running jobs whose lease is free:
requested cancellations are confirmed, exhausted jobs fail with
`ATTEMPTS_EXHAUSTED`, and others return to queued for redispatch. At most three
attempts run per job, including manual retries. Unexpected parser exceptions
fail safely as `PARSER_FAILURE`. Dramatiq time-limit interruption leaves the job
running for redelivery or reconciliation rather than marking it failed.

Implementation sources: [Starlette request forms](https://starlette.dev/requests/)
and [SQLAlchemy transaction management](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html).


## Text parser revision — T11

`text-v1` extracts paragraph passages as exact code-point slices of the UTF-8
original. It preserves internal CRLF, accents, combining marks, emoji, dialogue
and Markdown syntax. Leading/trailing paragraph whitespace is outside the stored
slice; normalization revision is `none-v1`. Evidence offsets are relative to the
immutable passage; source start/end separately locate it in the original text.

Chapter structure is conservative: explicit English `Chapter N` lines in TXT,
or ATX `#`–`######` chapter headings in Markdown outside fenced code. Ordinals
follow source order rather than trusting printed chapter numbers. Other Markdown
headings delimit paragraphs and are retained in the original, not emitted as
paragraph evidence. This is a paragraph adapter, not a CommonMark renderer or
scene detector. Missing chapters, unassigned preamble and unclosed fences produce
explicit warnings; unknown chapters are not silently assigned to chapter 1.

Initial parser ceilings are 2,000,000 code points, 20,000 passages, 2,000 chapter
markers and 16,384 code points per passage. Oversized/unusable sources fail with
safe parser-budget/no-passages outcomes rather than silent truncation. These
ceilings are not measured whole-book performance targets.

Parser outputs retain document/parser/normalization revisions, source-order
ordinals and explicit neighboring ordinals. Chapter and passage IDs are stable
within that exact document/parser revision. A changed parser/text revision must
produce a new output set rather than overwriting cited passage text.
