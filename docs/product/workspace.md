# Product workspace

The browser consumes the owned API contracts through the same-origin `/api/v1`
proxy. [Visual identity](../design/visual-identity.md) owns presentation;
[API contracts](../api/api-contract.md) own authorization and mutations.

## Library and uploads — T34

The library begins with a sign-in form for a locally provisioned account. The
session remains in its HttpOnly cookie; credentials and source text are never
saved in browser storage. Signing out or an expired-session response clears the
visible library. A failed library read has a reload action instead of presenting
an empty library as a successful result.

The upload form accepts the declared format, title and original file. It shows
transfer in progress without inventing a percentage. After the API confirms
storage, the book appears in the library. An uncertain upload can be resubmitted
with the same key and payload; editing the form begins a new request. Pagination
uses the server cursor and deduplicates already visible books.

Each book reads its latest source generation and ingestion job. Parsing,
extraction and search readiness appear separately. Parsing completion does not
announce that extraction or indexing is ready. Pending dispatch, safe error codes
and source warnings remain visible. The current implementation polls processing
state every two seconds while the book is displayed.

Retry is offered only for failed or cancelled parsing with attempts remaining;
cancel is offered for queued/running parsing. Each action submits the displayed
strong revision and a new idempotency key. A revision conflict reloads current
state and requires the reader to review it. Running cancellation remains
requested until the worker confirms the terminal outcome. A read failure disables
mutations until a fresh state arrives. Narrative retry remains PROP-06 and has
no invented browser control.

No external component source is copied for these controls. Native forms and
project components use the approved tokens and bundled fonts. Browser coverage
and its infrastructure boundary are recorded in the
[acceptance strategy](../testing/acceptance-strategy.md#library-browser-checks--t34).

## Reading boundary — T35

The chapter picker uses the owned current-generation chapter-number catalog.
Titles and excerpts do not appear in its options, including later chapters.
Its source revision, generation and parser revision identify the available
boundary. Unparsed sources return a visible not-ready result. Choosing a cutoff
must clear the prior entity selection, detail and context before loading eligible
data; whole-book and chapter scope remain distinct from story-time inputs.

Entity/context exploration, source reading, reconstruction/export and refinement
remain the subsequent T35–T38 browser increments.
