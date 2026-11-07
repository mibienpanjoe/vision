# Product workspace

The browser consumes the owned API contracts through the same-origin `/api/v1`
proxy. [Visual identity](../design/visual-identity.md) owns presentation;
[API contracts](../api/api-contract.md) own authorization and mutations.

## Conversation experience — Q26

**Status:** accepted product direction, 2026-10-30 (DEC-55); implemented as the
only browser path (Q31–Q50, 2026-11-07). The earlier library, book explorer,
reading-boundary selector and clickable preview are retired; their APIs remain
for compatibility and exact-source export.

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
outside this increment. The [API contract](../api/api-contract.md) owns the
conversation endpoints and their revision/idempotency rules.

## Implementation

| Area | Behavior | Owner |
|---|---|---|
| Entry | `/` opens the latest conversation or `/conversations/new`; the workspace capability bootstraps once across tabs with no credential fields. Lost access fails closed with a retry. | `app/page.tsx`, `components/session-provider.tsx` |
| Attach and ask | One composer: attach or drop a book and type; Enter sends, Shift+Enter adds a line. The draft clears on send and returns on failure. A question asked during preparation is stored and resumes. | `features/conversation/composer.tsx`, `use-composer.ts` |
| Understanding | Each turn is classified once into a typed intent from durable context (PROP-09: deterministic by default). Style edits refine; moment, wardrobe or scene changes reconstruct and verify. | API `services/conversations/intent.py` |
| Prompt card | The exact stored prompt with Copy prompt, Generate image, Sources and Export JSON; moment cards show the current moment and other moments' visible differences; earlier versions open collapsed and read-only. | `active-card.tsx`, `moment-options.tsx` |
| Sources | A modal sheet lists cited traits and shows the exact highlighted excerpt through the existing evidence API; Escape returns focus; it adds no chat message and closes on a newer card. | `source-drawer.tsx`, `features/reader/source-reader.tsx` |
| Images | One render per prompt version from the button or an explicit chat request; images keep their prompt version and stay labelled as earlier after edits. | `image-result.tsx` |
| Resume | The sidebar groups conversations by book, pages long histories, asks a new question on a saved book without upload and deletes a book in two steps. | `sidebar.tsx` |
| Recovery | Ambiguity offers the returned choices, missing evidence names what is absent, retryable failures offer Try again, preparation failure offers retry or replacement, stale tabs offer refresh. | `turn-recovery.tsx`, `live-workspace.tsx` |

The interface is deliberately minimal: whitespace over chrome, one status line,
secondary actions as quiet links, and speaker/heading labels kept for screen
readers. It is checked at 320px, 390px and desktop, in light and dark, with
reduced motion and 200% text (`tests/conversation-flow.spec.ts`).
