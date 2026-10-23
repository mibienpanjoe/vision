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

## Entity and context explorer — T35

Opening a book requires an explicit reading boundary before requesting entities.
Characters, places, objects and organizations come from the eligible API response.
Search filters only those eligible labels and aliases. Supported aliases and
candidate identities remain distinct; an ambiguous source mention offers named
candidate selections and never silently chooses an identity.

Changing boundary remounts the scoped explorer, clearing detail, subject, moment,
context and previous request results. Responses from the abandoned view cannot
populate its replacement. Generation mismatches require reloading the book.

Moment and scene context are user phrases, not an invented precomputed timeline:
DEC-38 derives events per question. The context form submits the selected entity,
moment and scene under the exact cutoff to the stored-visualization endpoint.
Only a resolved server result displays a saved revision receipt. Other outcomes
explain what is missing or failed. The profile, evidence inspector, export and
refinement below consume that stored result and exact request scope.

## Exact source reader — T36

An eligible entity mention opens its authorized bounded excerpt. Stored-result
attributes open their exact supporting spans under the active reading boundary.
Multiple references remain selectable; selecting highlighted source text selects
its matching attributes, including overlapping references. Highlights use Unicode
code points, retaining composed accents, decomposed characters and supplementary
characters without normalizing or rewriting the source.

The source reader validates returned highlight coordinates against the requested
span before rendering. Quotes render as text, never HTML. Page/section anchors
and original character coordinates identify the location when available. A
failed lookup removes the excerpt and shows the safe denial/mismatch result;
an old response cannot restore text after a new reference or scope is selected.
Boundary changes clear the result and open excerpt together. The reader never
widens scope to recover a missing reference.

## Reconstruction and export — T37

The composer accepts a query, explicit subject, moment, scene, canon-first or
interpretation mode, and optional visual style. Context outcomes offer buttons
that fill the relevant field; choosing another subject clears conflicting query
wording. Input changes clear the old result before another request can run.
An uncertain creation preserves its key/payload for replay. Failed or insufficient
outcomes retain editable inputs and never offer a stale result for export.

A resolved result displays the stored revision and scope, canonical, inferred,
disputed and unknown details, inference reasons, separately labelled creative
additions, exclusions, evidence and prompt/verification information. Model
verification and evidence-selection limits stay visible: when protected evidence
overflowed or was compressed under the context budget, the profile says so above
its evidence rather than only inside the verification details. The profile uses text
labels as well as selection color.

Export downloads exactly the stored server `VisualSpecification`, including its
scope, evidence and lineage, as JSON. It adds no browser-derived claims. Style
and interpretation do not relabel canonical traits. Refinement appends revisions
as described below.

## Refinement and history — T38

Saved specifications and revisions are requested with the active generation and
exact reading boundary. Incompatible subjects/labels never enter that filtered
history response. An explicitly opened historical revision is read-only, retains
its own scope/evidence/export, and points back to the current saved view for edits.
Changing boundary unmounts the whole history, result, source and refinement draft.

Refinement sends the displayed revision, style/mode and selected canonical locks.
It waits for the stored revision response before updating the profile. A stale
tab cannot save again until the reader reloads the current revision; that action
loads its locks/mode and retains the draft style for review. Uncertain network
outcomes retain their exact key/payload/revision for replay. A source or processing
change requires a new reconstruction instead of silently restyling stale inputs.
