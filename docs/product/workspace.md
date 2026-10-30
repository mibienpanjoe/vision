# Product workspace

The browser consumes the owned API contracts through the same-origin `/api/v1`
proxy. [Visual identity](../design/visual-identity.md) owns presentation;
[API contracts](../api/api-contract.md) own authorization and mutations.

## Conversation experience — Q26

**Status:** accepted product direction, 2026-10-30 (DEC-55); implementation and
runtime acceptance pending. The sections after this contract describe the
existing library/explorer implementation, not delivery of this conversation.

Open directly into a private, remembered conversation. Attach a book and ask in
one composer; detect its title and format. Sign-in, entity browsing and a reading
limit are not prerequisites. A quiet sidebar opens recent books and conversations.
Whole-book evidence eligibility is the default; it does not send the book to a
provider or permit blending incompatible ages, outfits or story moments.

The primary result is one evolving image prompt card, useful independently of an
image purchase. Copy prompt copies only the active stored prompt; Generate image
is an adjacent, explicit action. Sources, prior versions and exact structured
export open on demand. A card revision references an immutable specification;
an old image stays attached to the prompt revision that actually generated it.

### States and actions

| State | Observable behavior and next action |
|---|---|
| First visit | One labelled composer and Attach book action; no credential, chapter or entity setup. Workspace initialization failure keeps the draft and offers retry without exposing a shared library. |
| Attach and ask | Drop/select a book and type together; automatic metadata, editable draft, one submission. A replacement attachment does not silently discard the question. |
| Reading the book | Show actual preparation status. Persist a submitted request while waiting and resume on readiness; failure preserves it with Retry or Replace book. No fake percentages. |
| Resolving identity | Supported aliases share the same subject. Genuine ambiguity asks one short question with contextual options; choosing one continues the pending request. No entity-cleanup chore. |
| Prompt ready | A readable, copyable supported prompt; omit unknown details. Offer optional, normally two or three, evidence-backed moments only when visual differences exist. |
| Moment switch | One selection applies a server-issued moment action without another Submit. Indicate selection and pending state; retain the prior prompt until a verified replacement commits. |
| Refinement | Typed followups retain subject, clothing/style and moment context after reload. Presentation edits preserve claims; changed subject/scene reconstructs. A compact receipt accompanies the next version. |
| Sources open | Drawer/sheet shows the exact cited passage and highlight in place. Closing restores invoker focus and reading position; it adds no chat turn. |
| Image pending | Only an explicit Generate image action starts a render of the active verified revision. Show real status; draft typing remains available. |
| Image finished or failed | Display the attached image and Download, or a safe actionable error. An uncertain paid outcome is distinct from a rejected request and never automatically resubmitted. |
| Return visit | Resume the same private book, ordered thread, context, active card and images across tabs/browser close/service restart within the documented session policy. Never claim legacy books for a new visitor. |
| Failure or stale tab | Preserve draft and prior valid prompt. Distinguish absent evidence, service failure and stale revision; refresh explicitly before conflicting edits. Late results cannot replace newer work. |
| Narrow screen | History and sources open on demand; keep composer and prompt usable at 320px and 200% text without horizontal overflow. Every action supports keyboard/touch and named selected/pending states. |

Status changes must not pull a reader away from an earlier message. Expand details
locally and offer Return to latest when appropriate. Restore focus after drawers
and preserve an editable draft during pending work. Use readable contrast, visible
focus and reduced-motion preferences in light and dark themes.

### Grounding and persistence boundaries

Missing eye color does not discard supported clothing. No supported appearance,
unresolved identity and unavailable provider are separate outcomes with distinct
recovery. Do not promote rumor, metaphor, someone else's possessions or conflicting
details to canonical traits. Whole-book eligibility still requires temporal and
holder verification; existing explicit-cutoff API clients retain their semantics.

Reuse owner-scoped, same-origin APIs with conditional idempotent mutations and
durable dispatch intent. Store messages, context, turn receipts and immutable
card revisions; browser-only transcripts do not satisfy remembered conversation.
Keep original bytes and exact Unicode source spans immutable. Preserve the
existing local-ingestion, selected-excerpt disclosure and finite render budgets.
Upload, suggestions, navigation, refinements and retries must not implicitly buy
an image. Public hosting, cross-device access and direct prompt editing remain
outside this increment. Concrete endpoints and session lifetime are implementation
proposals; this contract does not claim those resources already exist.

### Controlled preview — Q27

An opt-in `/preview/conversation` entry point demonstrates the interaction using
only the synthetic story. `make conversation-preview-check` builds separately
under `.next-preview` and runs its Chromium checks; start that preview with
`VISION_CONVERSATION_PREVIEW=1 pnpm --dir apps/web exec next start --hostname 127.0.0.1 --port 13001`. Without that runtime flag the route returns 404. The normal library is
unchanged. Preview controls choose explicit sample outcomes; attachments supply
only a display filename and are never uploaded or parsed. Responses, image
placeholders and sessionStorage history are simulated, not real extraction,
durable workspace access, paid generation or cross-tab concurrency proof.

The preview exercises moment selection, source focus restoration, copy, immutable
sample versions/export, earlier-image association, preparation retry/replacement,
ambiguity, missing evidence, unavailable service, stale version and uncertain
image outcomes. Unknown image acceptance survives reload without another send.
Actual storage failure leaves the in-memory draft usable. Real resources and
provider-quality acceptance remain later implementation work.

## Library and uploads — T34

The library opens through the remembered private workspace capability (Q33a).
Normal entry has no sign-in, sign-out or account-name fields. Bootstrap is
serialized across browser tabs and renews the HttpOnly session. Browser storage
contains only a noncredential initialization marker; lost established access
fails visibly and uses trusted local recovery instead of allocating a new owner.
Temporary network failure retains mounted content and drafts. A failed library
read has a reload action instead of presenting an empty library as success.
The first-visit conversation composer remains pending the conversation resources
and their authoritative browser consumer; the current entry still shows the library.

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

Opening a book defaults to whole-book evidence eligibility (Q33a). The compatible
chapter selector remains available in this legacy explorer until replacement.
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
