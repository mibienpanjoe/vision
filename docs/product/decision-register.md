# Decision register

**Recorded:** 2026-10-19. Baseline means selected design, not implemented behavior.

## Baseline decisions

| ID | Decision | Authority / owning detail |
|---|---|---|
| DEC-01 | Source-grounded visual reconstruction; structured JSON is the primary output | Overview §§1–5; [requirements](requirements-and-acceptance.md) |
| DEC-02 | Identity, state, context, source order, and story chronology are separate | Overview §3; [narrative contract](../narrative/narrative-contract.md) |
| DEC-03 | Source spans remain authoritative; the narrative model is derived and revisable | Retrieval §2; [canonical model](../data/canonical-model.md) |
| DEC-04 | FastAPI modular monolith, Next.js/TypeScript frontend, PostgreSQL | Overview §§6,9; [ADR-0001](../adr/0001-modular-monolith.md) |
| DEC-05 | PostgreSQL FTS + pgvector + entity evidence, RRF, reranking, reconstruction, verification | Retrieval selected baseline; [ADR-0002](../adr/0002-temporal-hybrid-retrieval.md) |
| DEC-06 | Docling plus format adapters; retain original files and structural metadata | Overview §6; [ingestion](../ingestion/ingestion-contract.md) |
| DEC-07 | Redis + Dramatiq for background jobs; SQLAlchemy + Alembic for persistence | Overview §6; [architecture](../architecture/system-architecture.md) |
| DEC-08 | Pydantic/JSON Schema; generate frontend contracts from executable schemas | Overview §§6,9; [API draft](../api/api-contract.md) |
| DEC-09 | Narrow, interchangeable provider adapters and processing versions | Overview §6; [architecture](../architecture/system-architecture.md) |
| DEC-10 | Whole-book and read-through-chapter modes, including derived-data isolation | Overview §3.5; [narrative contract](../narrative/narrative-contract.md) |
| DEC-11 | Canon-first and creative interpretation; optional image rendering follows JSON | Overview §§3.4,12; [visual specification](../visualization/visual-specification.md) |
| DEC-12 | Private uploads; local files in development and S3-compatible deployment storage | Overview §§6,11; [security](../../SECURITY.md) |
| DEC-13 | shadcn/ui base with selected specialized agent-interface components; Agents Kit is a named reference | Maintainer instruction, 2026-10-19; [visual identity](../design/visual-identity.md) |
| DEC-14 | Supplied book-and-doorway logo is the identity direction; use image generation for initial derivatives and inspect outputs | Maintainer instruction, 2026-10-19; [visual identity](../design/visual-identity.md) |
| DEC-15 | Approve the retained book-and-doorway logo assets; keep the documented 16 px/favicon and transparent-inverse limitations | Maintainer approval, 2026-10-19; [asset manifest](../../assets/brand/asset-manifest.md) |
| DEC-16 | Inter for UI, Source Serif 4 for literary text/headings, Geist Mono for structured output; warm paper/charcoal/gold light and dark themes; dark by default with system, light and dark choices retained (maintainer, 2026-10-23) | Selected under maintainer delegation, 2026-10-19; [visual identity](../design/visual-identity.md) |
| DEC-17 | Public GitHub repository; uploaded works and runtime data remain private | Maintainer instruction, 2026-10-19; [security](../../SECURITY.md) |
| DEC-18 | Keep overview in `docs/product/` and detailed retrieval strategy in `docs/architecture/`, with no root duplicates | Selected under maintainer instruction, 2026-10-19; [documentation map](../documentation-map.md) |
| DEC-19 | D0: Python 3.12.14/uv 0.12.15, Node 24.12.0/pnpm 10.28.0, PostgreSQL 17/pgvector 0.8.7, Redis 8.2.10; generated locks and digest-pinned images | T01 implementation selection; [operations](../operations/development-and-operations.md#selected-toolchain--d0) |
| DEC-20 | Adopt PROP-01: immutable passage text with code-point `[start,end)` spans; reject normalization/quote mismatch | T02; [ingestion](../ingestion/ingestion-contract.md#source-span-proposal--prop-01) |
| DEC-21 | Adopt PROP-02: compatible stage generations, atomic conditional publication, retained old citations | T02; [ingestion](../ingestion/ingestion-contract.md#reprocessing-proposal--prop-02) |
| DEC-22 | First slice uses English synthetic text; explicit temporal support is required for canonical carry-forward; cutoff follows dependency closure | T02; [narrative contract](../narrative/narrative-contract.md) |
| DEC-23 | Adopt PROP-03 shared outcomes/errors; exact ETag/If-Match, scoped durable idempotency and explicit request conflict resolution | T02; [API conventions](../api/api-contract.md#selected-first-slice-wire-conventions) |
| DEC-24 | Use the installed FreeLLM API for LLM calls; verify role/model capabilities and source handling before live integration | Maintainer decision, 2026-10-19; [operations](../operations/development-and-operations.md#local-model-gateway) |
| DEC-25 | Local-only application; external hosting/deployment is outside delivery scope; private local storage is the active baseline | Maintainer decision, 2026-10-19; [operations](../operations/development-and-operations.md#delivery-scope) |
| DEC-26 | Local CLI-provisioned accounts, scrypt passwords and 12-hour opaque DB sessions; same-origin loopback web proxy, HttpOnly/SameSite Strict cookie and explicit mutation Origin checks | T07 implementation choice under local-only scope; [API authentication](../api/api-contract.md#local-authentication--t07) |
| DEC-27 | First upload boundary: UTF-8 TXT/Markdown, 8 MiB/source, 60-second transfer, private opaque originals; title 256 code points and page size 100 | T10 engineering limits under OPEN-05; [ingestion](../ingestion/ingestion-contract.md#first-upload-input-boundary--t10) |
| DEC-28 | PDF via Docling 2.140.0 (pypdfium2 backend, local Heron layout model, CPU-only PyTorch); OCR and table structure disabled; text-layer-free PDFs fail explicitly | T14 under maintainer selection, 2026-10-20; [ingestion](../ingestion/ingestion-contract.md#pdf-parser-revision--t14) |
| DEC-29 | EPUB via a project XHTML adapter (container validation before parsing, defusedxml for package XML, network-free lxml HTML for spine documents) rather than Docling's EPUB backend; spine order with document/fragment anchors | T15; [ingestion](../ingestion/ingestion-contract.md#epub-parser-revision--t15) |
| DEC-30 | Provider envelope: frozen tool-free requests, sources only as a quoted JSON data block, strict schema-versioned outputs, seven distinct outcomes, side-effect-free execution persisted with canon; default 60 s / 48,000 chars / 2,048 output / 16,000 total tokens | T17 engineering bounds under OPEN-05; [architecture](../architecture/system-architecture.md#provider-envelope--t17) |
| DEC-31 | Entity derivation: versioned per-generation derivations, chapter-aligned batches, verbatim quote grounding with counted rejections, kind+label unification only, explicit candidates and `same_as` links, attempt-guarded atomic publication | T18; [narrative contract](../narrative/narrative-contract.md#entity-derivation--t18) |
| DEC-32 | Events depend on an explicit entity derivation; modality kept per event; stated relations only; partial order over fact/memory events with cycle and overlap conflicts reported as inconsistent; earlier events passed as non-citable `k:n` data | T19; [narrative contract](../narrative/narrative-contract.md#event-derivation-and-partial-chronology--t19) |
| DEC-33 | Visual facts: explicit/inferred support only, polarity and modality kept, lexical attribution/owner/negation/question gates before storage, canonical = explicit+affirmed+fact/memory, conflicts recorded unresolved at shared events | T20; [narrative contract](../narrative/narrative-contract.md#visual-fact-derivation--t20) |
| DEC-34 | Narrative browse reads the latest succeeded derivation chain of the current generation and filters every derived record by dependency closure at the chapter cutoff; labels must come from visible mentions; `409 NARRATIVE_NOT_READY` before extraction | T21; [API](../api/api-contract.md#narrative-browse--t21) |
| DEC-35 | Narrative completion: per-generation job queued with parse publication, entity→event→fact stages through the worker, readiness only on full success, live provider opt-in via `VISION_NARRATIVE_PROVIDER=live` | T22; [ingestion](../ingestion/ingestion-contract.md#narrative-completion--t22) |
| DEC-36 | Query-time fallback provider for minimal-disclosure consolidation: Groq (`gpt-oss-120b`) with Zero Data Retention, over cutoff-filtered excerpts only | Maintainer decision, 2026-10-20; [research](../research/local-first-processing.md#10-spike-results-2026-10-20) |
| DEC-37 | Accept ADR-0003: ingestion is local (GLiNER2 entities with deterministic identity rules, fastcoref per chapter, appearance patterns, PostgreSQL FTS plus EmbeddingGemma-300M with measured fusion weights); facts are consolidated at query time from cutoff-filtered excerpts through Groq with ZDR; local models pinned, no unmeasured quantization; the FreeLLM gateway (DEC-24) may process synthetic fixtures only | Maintainer decision, 2026-10-21; [ADR-0003](../adr/0003-local-ingestion-minimal-disclosure.md) |
| DEC-38 | DEC-37 contract: local `entities` and `appearance` ingestion stages with versioned identity rules; identity links need a supporting passage and apply from it onward (local coreference or explicit reveal patterns; consolidation may propose scoped, quoted links); events and visual facts as query-scoped `consolidation` derivations over cutoff-filtered passages in one combined-schema call, reused by scope and passage digest | Maintainer decision, 2026-10-21; [narrative contract](../narrative/narrative-contract.md#local-ingestion-and-query-time-consolidation--dec-38) |
| DEC-39 | Request resolution: chapter references match heading numbers and may narrow but never widen the reading boundary; story ages/phrases and scene context are separate plan fields; subjects resolve only from cutoff-eligible names, aliases and visible `same_as` links, ambiguous surfaces offer choices; structured/text disagreements return `needs_context`; an unspecified moment is never chosen by the planner | T23 engineering rules (`query-plan-v1`, English); [API](../api/api-contract.md#visualization-request-resolution--t23) |
| DEC-40 | Lexical retrieval: stored English `tsvector` with GIN over passages; entity-linked passages from resolved mentions only; subject-linked appearance sentences are protected candidates; name phrases limited to surfaces unique to the subject at the cutoff; ranking by distinct names/terms matched, then cover density; every path scoped in SQL by document, parser revision and boundary | T24; [architecture](../architecture/system-architecture.md#lexical-and-entity-linked-retrieval--t24) |
| DEC-41 | Semantic index: local `index` stage after appearance; EmbeddingGemma-300M `57c266a7` fp32 CPU, document/query prompts, 512-token window, 768-d pgvector rows per derivation; queries only against the same embedder version; appearance-oriented expansions per entity kind; exact cosine scans scoped by document, parser revision and boundary, without entity filtering; `search_ready_at` on index success | T25; [architecture](../architecture/system-architecture.md#semantic-indexing-and-retrieval--t25) |
| DEC-42 | Fusion and selection: weighted RRF (k 60) with semantic 1.0, lexical 0.5, entity and appearance 0 (they supply anchors and protection); budget 20 whole passages / 20,000 characters; protected sentences reserved first, category coverage within the top 40, then rank; duplicates sent once; explicit `complete`/`compressed`/`truncated`/`protected_overflow` outcomes. Measured on Jekyll: recall@5 0.74, selection recall 0.93 against 0.79 for whole-protected-first | T26 measurement; [architecture](../architecture/system-architecture.md#fusion-and-protected-selection--t26) |
| DEC-43 | Consolidation: one Groq `gpt-oss-120b` call over the budgeted in-boundary selection plus backward attribution context; derivation scope stored with a digest that ends its version (reuse by scope and spans); events/facts through the existing publication; identity links scoped to the consolidation; new `rate_limited` outcome with one bounded `retry-after` wait (≤ 20 s); removal words negate and hedged fact/memory claims are refused as `speculative` | T27; [narrative contract](../narrative/narrative-contract.md#local-ingestion-and-query-time-consolidation--dec-38) |
| DEC-44 | Appearance state: direct claims canonical (disputed when they disagree); only the latest earlier acquired change carries, as inference; scoped identity traits and intervals stay at their events; untimed stable claims are inferences; scene claims never carry; removals, later and unordered claims excluded with reasons; unspecified moment with several canonical events returns those events as choices; the moment is the consolidation's grounded `requested_event`, never a label guess | T28; [narrative contract](../narrative/narrative-contract.md#appearance-state--t28) |
| DEC-45 | Scene composition: members reconstructed separately at one event; people and places present only when the event names them or a claim ties them to it and not stated absent; objects present when described at the event or held by a present member, excluded when their carrier is absent; world context only from present places, otherwise `setting` unknown; requested but unsupported participants reported | T29; [narrative contract](../narrative/narrative-contract.md#scene-and-world--t29) |
| DEC-46 | Verification: per-fact deterministic re-checks (owner, evidence, span, boundary incl. linked events, attribution, canonical modality, asserted value, moment) remove with stable reasons; optional quote-bound adjudication with passage context can only remove or mark entailed; provider failure leaves the deterministic result marked `unavailable`; prompt gate refuses excluded values, settled disputes, unsupported or missing locks, quoted creative text and instruction-like text | T30; [visual specification](../visualization/visual-specification.md#attribute-and-prompt-gates--t30) |
| DEC-47 | Visualization compose: synchronous `POST /v1/works/{work_id}/visualizations/compose` returning 200 with `resolved`/`needs_context`/`insufficient_evidence`/`failed`; `vision-spec-1.0` with lineage, scope, subject/participants/world members, exclusions, unknowns, creative additions, prompt intent and verification summary; choices carry their request `field`; interpretation adds labelled creative choices without changing canon; no stored result until T32 | T31; [API](../api/api-contract.md#visualization-compose--t31) |
| DEC-48 | Stored visualizations: only resolved results are stored (201 + ETag); other outcomes 200 without reservation; key scoped to owner+work with request fingerprint (replay / 409); immutable revisions keep full result, generation, parser revision and consolidation; owner-scoped list/read/history with 404 otherwise | T32a; [API](../api/api-contract.md#stored-visualizations--t32a) |
| DEC-49 | Adopt PROP-05: resolved results cached per owner under the hash of work, generation, cutoff, subject/participants, moment, context, creative mode, style, locks and every processing version (derivations in use, prompts, models, gates, spec, fusion weights); lookup only after the plan re-checks ownership and current generation | T32b; [architecture](../architecture/system-architecture.md#scoped-result-cache--t32b) |
| DEC-50 | Presentation refinement uses a conditional, idempotent revision append: style/mode and canonical locks only; profiles/evidence remain unchanged, provenance and prompt gates rerun; changed source or derivation inputs require a new reconstruction; replay returns its captured revision | T38; [API](../api/api-contract.md#presentation-refinements--t38) |
| DEC-51 | D5 rendering: OpenAI `gpt-image-2` (default) or `gpt-image-1` via `VISION_RENDER_MODEL`, low quality, 1024×1024 PNG with `OPENAI_API_KEY`; FLUX.1-schnell through the Hugging Face router (`nscale` route) with `HF_TOKEN` remains selectable; explicit opt-in by `VISION_RENDER_PROVIDER`; only the specification's gated `generation.prompt` is sent (derived attributes, locks and style; never source quotes, spans, titles or owner identifiers); negative prompt not sent; at most five reservations per owner; live acceptance (T40, T42) is limited to five requests in total; one charged call per reservation, no automatic retry, unanswered sends recorded as `acceptance_unknown` | Maintainer decision, 2026-10-22; [API](../api/api-contract.md#image-rendering--t40) |
| DEC-52 | Work deletion: owner-requested, immediate and irreversible; the work and everything derived from it (original, passages, indexes, narrative, specifications, cache, images, model-run records) are absent at once and purged after in-flight jobs stop; only a minimal tombstone (owner, work ID, expected revision, deletion/original-upload idempotency keys, lifecycle times, dispatch/attempt metadata and status; no content or hashes) remains; account deletion is a later CLI follow-up | Maintainer decision, 2026-10-25; [API](../api/api-contract.md#work-deletion--t46) |
| DEC-53 | Authorize opt-in OpenAI `gpt-6-luna` text integration and a finite synthetic evaluation using the existing project key. Responses API, strict JSON, no extra reasoning by default, no tools or conversation history, `store=false`; local ingestion and all grounding/spoiler gates remain. Groq stays the default; this does not authorize private-book excerpts to OpenAI or assert ZDR | Maintainer instruction, 2026-10-27; [operations](../operations/development-and-operations.md#openai-text-evaluation--q01) |

## Workspace implementation

T34 consumes DEC-23/26/27 without changing lifecycle policy: native project forms,
same-origin session requests, two-second processing polling, server-confirmed
retry/cancel, and separate parse/extraction/index states. No Agents Kit source is
copied, so D4 has no imported-component license selection in this increment.
The [workspace contract](workspace.md) owns these controls. Narrative retry remains
PROP-06; parsing retry does not claim to retry a failed narrative job.
T35's chapter catalog is an owned, paginated current-generation read exposing
numbers and IDs without narrative titles. This implements DEC-10's reading boundary
without disclosing future chapter labels; it does not enumerate story chronology.
T36 consumes DEC-20/23 through the bounded evidence endpoint: browser highlights
use code points, text remains escaped, and a failed/stale reference clears its
excerpt without widening the reading boundary.
T37's natural-language consumer includes a query SHA-256 in both result-cache
and consolidation identity: the reader's exact words affect the provider input
even when the structured plan is identical. Existing revisions remain immutable.
T38 snapshots each revision's request and the exact entity/appearance/index
inputs; structured exclusions remain with the specification for subsequent prompt
gates. Existing creation keys keep replaying revision 1 rather than a later edit.

T40a implements provider-neutral owned render reservations and conditional
cancellation receipts; T40 consumes DEC-51 with the adapter, dispatch and worker.
The Hugging Face account had no Inference Provider credit (HTTP 402), so the
maintainer selected OpenAI the same day; FLUX stays as an alternative selected by
environment. Two further live requests were approved on 2026-10-22 to compare
`gpt-image-1` and `gpt-image-2` on the single-scene prompt; other models are refused.
`gpt-image-2` drew the roofless house and the compass correctly, so the maintainer
made it the default on 2026-10-23; `gpt-image-1` stays selectable.
Provider retention follows their terms and has not been verified as
zero-retention; trait values in the prompt can echo short source
wording as derived attributes.

T46 implements DEC-52 with recoverable retention-queue cleanup. The minimal
tombstone also retains the original upload key so a delayed upload retry cannot
recreate a physically deleted book. It retains no source hash or content.

T47 consumes DEC-25/52 with offline local snapshots, separate deletion-ledger
export and restoration into a new target. Restore revokes sessions, reapplies
later deletions before access, and conservatively settles both queued and
running image attempts as acceptance unknown. Snapshot/copy frequency, encryption
and expiry remain operator-managed; no external backup service is selected.
T48's closing recovery audit adds an independent checksum to deletion-ledger
exports: corrupted ledgers are refused before restoration can write data.
The closing cost audit preserves DEC-51's cap in an account-level consumed
reservation counter, independent of deletable history. The latest ledger also
checkpoints that aggregate, so neither book purge nor restore refunds usage.
No book content, work reference or per-book model-run history is retained there.
The final review also makes backward attribution expansion consume the configured
DEC-42 budget and gives DEC-52's row-purge transaction a bounded 60-second
statement timeout; request connections keep their two-second bound.

Q03's larger-output synthetic evaluation exposed a dropped inference reason:
the assumption was stored with the fact but omitted from reconstruction's
in-memory claim. The fix preserves that assumption through the response, keeps
direct inferences non-canonical, and excludes unexplained inferences, consuming
DEC-44 and the existing specification contract without changing either policy.

## Proposed elaborations

These make implementation discussions concrete without pretending the source
documents fixed all details.

| ID | Proposal | Resolve in |
|---|---|---|
| PROP-04 | First vertical slice uses a small synthetic TXT/Markdown narrative before format expansion | First implementation increment; [roadmap](implementation-roadmap.md) |
| PROP-06 | Owner-facing narrative retry route with `If-Match` and `Idempotency-Key`, mirroring ingestion retry | Before real-book narrative use |
| PROP-07 | Reconstruction acceptance targets on the synthetic corpus: zero blocking failures (incorrect canonical, spoiler leak) as a hard gate; canonical recall and outcome agreement measured per live run, starting from the T33 baseline (14/23, 13/17) and reviewed before Phase 7 limits | Maintainer review before Phase 7 (OPEN-05) |
| PROP-08 | Measured T44 budgets: keep `VISION_MAX_ACTIVE_WORKS` at 3 (one serial worker, about 16 minutes per novel); lower `VISION_CONTEXT_CHARACTERS` to 12,000 for the free Groq tier (no measured recall loss down to 10,000; 18,500+ characters were refused 4/4, 12,700 and below accepted 3/3) or keep 20,000 on a paid tier; skip the immediate malformed-output retry when the provider is per-minute limited | Maintainer review (OPEN-05); [measured budgets](../operations/development-and-operations.md#measured-budgets--t44) |

## Open decisions

| ID | Question | Needed before |
|---|---|---|
| OPEN-01 | Resolved by DEC-26; later work consumes the validated ActorScope | Any network-accessible real upload flow |
| OPEN-02 | Private-book source handling resolved by DEC-37 (no book text leaves the machine at ingestion; query-time excerpts to Groq with ZDR). Groq rate-limit handling, per-question token ceilings and the daily question budget remain open | Query-time consolidation |
| OPEN-03 | First language resolved by DEC-22 (English); broader languages/configurations remain open | Lexical indexing and multilingual claims |
| OPEN-04 | Resolved for the first slice by DEC-22; revisit only with an explicit changed decision | Temporal reconstruction implementation |
| OPEN-05 | Concrete upload/expansion/time/token/cost/candidate limits and performance targets (first reconstruction baseline: T33; book-length measurements and PROP-08: T44) | Accepting untrusted workloads; then calibrate with measurements |
| OPEN-06 | Runtime/package choices resolved by DEC-19, PDF parsing by DEC-28 and the embedding model/dimension by DEC-41; OCR coverage, vector truncation and ANN settings remain open | Reproducible development environment |
| OPEN-07 | Shared revision/idempotency resolved by DEC-23 and work deletion by DEC-52; account deletion and time-based retention remain open | Executable API and persistent lifecycle |
| OPEN-08 | External deployment excluded by DEC-25; local recovery, retention and deletion remain required | External deployment |
| OPEN-09 | Project license, exact component selections, final wordmark/vector assets, and any future optically simplified favicon | Redistribution or relevant implementation increment |
| OPEN-10 | Resolved by DEC-51; provider-side retention verification and image deletion remain open | Retention and deletion lifecycle (T46) |

OPEN-04 is resolved conservatively by DEC-22. PROP-01/02/03 were promoted to
DEC-20/21/23; executable tests and runtime proof still belong to their task owners.

## Deferred scope

Rendered visuals come after grounded JSON. Voice, animated agent mascots,
microservices, and multi-agent orchestration are not implied by selecting an
agent-interface component source. Production readiness has not been established.

## Changes

Record a changed decision with its reason and affected requirements, contracts,
tests, and data migration. Expensive architecture changes receive a new ADR;
superseded ADRs remain available. Do not reopen the selected retrieval stack as
an A/B comparison without an explicit decision to revisit it.

Q07 implementation refinement of DEC-38/53: adjudication preserves the complete
request, scene and grounded resolved event instead of dropping the scene when a
broad moment exists. `adjudicate-v3` invalidates cached checker results; source
and spoiler boundaries and canonical/inferred policy are unchanged.

Q08 implements the authorized quality refinement within DEC-38: bounded,
cutoff-scoped entity refs and unique visible aliases normalize model subjects and
participants before existing publication gates. `consolidate-v6` separates old
derivations and caches. Ambiguous titles and unquoted identities remain unresolved.

Q09 clarifies DEC-38 extraction instructions and schema descriptions without
changing canonical/inferred policy or splitting the combined provider call.
Prompt/schema versions invalidate prior consolidation reuse.

Q10 refines source-bound checking: selected cutoff-safe change passages may
justify rejection, while entailment still needs the claim's own citation.
`adjudicate-v4` requires complete valid verdict coverage/context for `applied`
and complete per-trait coverage for `entailed`; otherwise existing deterministic
results remain explicitly unchecked/unavailable. No checker verdict admits or
promotes a claim. Shared context obeys the existing input bounds.
