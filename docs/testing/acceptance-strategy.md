# Acceptance and verification strategy

**Status:** executable unit, contract, PostgreSQL/Redis/worker and browser checks
cover the local non-rendering workspace. Live extraction/reconstruction evidence
and its measured recall limits are recorded below; deterministic adapters remain
the reproducible regression oracle. Optional rendering and release-environment
acceptance require their separate gates.
The [requirements](../product/requirements-and-acceptance.md) own product promises;
this page owns how to demonstrate them without relying on attractive output.

## Synthetic narrative fixture

The [versioned synthetic story](../../apps/api/tests/fixtures/narrative/story.md)
and [annotations](../../apps/api/tests/fixtures/narrative/expected.json) provide a short narrative with Arthur as a child, an injury during a war,
armor removed before a home scene, a later chapter flashing back to childhood,
two people called captain, an object attributed to another person, a rumor,
a metaphor, and a damaged/rebuilt building. Include explicit unknown traits,
contradictions, and a fact resolved only beyond a reading cutoff.

The annotations identify entities, exact spans, admissible temporal relations,
scope, support type, expected inclusions/exclusions, and unresolved ambiguity.
Add accents and supplementary Unicode characters to exercise source offsets.
Keep this corpus synthetic; do not commit private books as convenient fixtures.

Run the corpus checks from the repository root using the selected Python:

```sh
python3.12 -m unittest discover -s apps/api/tests -p 'test_fixture_annotations.py' -v
```

The standard-library tests require no package installation. They check the source
SHA-256, exact code-point slices, paragraph and chapter mapping, reference integrity,
disjoint expected outcomes, scope/owner compatibility and cutoff eligibility of
selected facts. The corpus contains 14 passages, 33 spans, eight entities,
eight events, 25 facts, one dinner scene and 17 outcome cases. Versions and
synthetic provenance are embedded in the annotation file. Review changes to the
story and annotations together; never regenerate an oracle from model predictions.

T03 ran three passing integrity tests, a Node code-point probe for all 33 spans,
and temporary mutation probes that rejected quote corruption, unknown entities,
late cutoff evidence, wrong ownership and stale source identity. These establish
fixture consistency. The expected temporal states, ambiguity and support labels
were reviewed against the story. Extraction and reconstructed outputs were
evaluated separately in T22/T33. Client contracts and DOM highlighting have their
own executable checks below.

## Scenario matrix

| Scenario | Requirement IDs | Observable proof |
|---|---|---|
| All four input adapters | REQ-02, REQ-04 | Exact quoted slices, structure warnings, original revision mapping |
| Reprocessing after changed segmentation | REQ-04, REQ-17, REQ-18 | Old citations remain meaningful; incompatible states cannot be reused |
| Duplicate job delivery, retry, cancellation | REQ-03, REQ-18, REQ-19 | Durable terminal outcome, no duplicate facts or false completion |
| Alias and ambiguous captain | REQ-05, REQ-12 | Supported identity merge or admissible options; no indiscriminate title merge |
| Childhood before injury | REQ-06, REQ-07, REQ-09 | Later scar excluded despite a high semantic similarity score |
| Battle versus home | REQ-07, REQ-10 | Correct attire and ownership; armor removal interpreted correctly |
| Damaged then rebuilt house | REQ-06, REQ-09 | Requested building version or explicit unresolved chronology |
| Fact scattered across chapters | REQ-08, REQ-14 | All annotated material traits found and cited; low-rank protected fact survives |
| Later flashback and derived identity leak | REQ-11, REQ-18 | Ineligible passages, entity merges, context labels, facts, and cache states absent |
| Dream, rumor, negation, wrong owner | REQ-05, REQ-13 | Unsupported canon rejected with appropriate uncertainty |
| Conflicting or missing attributes | REQ-12, REQ-14, REQ-15 | Conflict/unknown remains visible; creative completion separately labeled |
| Schema-valid hallucinated attribute | REQ-13, REQ-16 | Grounding gate rejects it despite structural validity |
| Style refinement of locked fact | REQ-15, REQ-16 | Canon remains unchanged; final prompt does not contradict profile |
| Provider failure and changed adapter | REQ-17, REQ-19, REQ-21 | Safe bounded failure, explicit versions, equivalent domain contract |
| Cross-owner library/job/evidence/cache/asset access | REQ-01, REQ-18 | Every access path denies disclosure, including indirect references |
| Prompt injection and hostile upload | REQ-19, REQ-22 | No tool/credential access or unbounded parser work |
| Optional render | REQ-20 | Real image/specification linkage and visible provider failure/retry outcome |

## Evidence levels

- **Documentation checks:** relative links/anchors, JSON syntax, fences, IDs,
  status consistency, and source preservation. These prove document quality.
- **Domain tests (pytest):** deterministic fixtures for chronology, offsets,
  dependency eligibility, ownership, fusion/protected evidence, and validation.
- **Infrastructure integration:** actual PostgreSQL FTS/pgvector, persistence,
  Redis/Dramatiq execution/recovery, private storage, and cache boundaries.
- **Provider integration:** named live role/model, bounded corpus, extracted
  spans compared to annotations. Mocks do not prove actual extraction quality.
- **Product checks (Playwright):** actual browser/API/database/worker flow,
  source highlighting and export, narrow layouts, keyboard behavior, empty and
  error states. Optional image rendering needs its own real provider check.
- **CI/deployment:** only report CI success from a real run, and deployment
  readiness from checks against the intended deployed environment.

Compare extraction and retrieval against annotated expected facts, including
material omissions and incorrect inclusions. Record the fixture and processing
versions. Numerical quality, latency, and cost thresholds remain OPEN-05; do not
invent target percentages or claim exhaustive recall from one synthetic story.

## Current verification boundary

The suites below cover database readiness/migrations, ownership/sessions,
four-format ingestion, real broker/worker execution, scoped narrative/retrieval,
stored specifications, source spans, browser workflows, optional rendering,
deletion and restoration. Commands and isolated fixture
setup belong to [operations](../operations/development-and-operations.md#local-commands-and-verification).
Deterministic adapters, live local models, live remote providers and browser
checks establish different evidence levels. Measured model recall and pixel
limitations remain explicit in the relevant sections; these checks do not prove
universal fidelity, full WCAG coverage or production security. Check the actual CI run for
a named commit; local success alone is not remote CI evidence.


## Source ingestion checkpoint

Real database/API/storage tests cover owner-scoped multipart upload, idempotent
creation, private original reads, bounded library pages and interrupted-upload
reconciliation, including lost commit acknowledgements. A real Redis/Dramatiq
worker persists every annotated paragraph/chapter from the retained synthetic
story. Duplicate delivery retains one committed output set; known parse failures
and fingerprint mismatches remain explicit terminal outcomes.

The evidence API resolves all annotated exact spans against those persisted
passages and checks owner, source/parser revision, quote, context size and chapter
cutoff. Python/Node conformance includes an emoji highlight and rejects an altered
excerpt. A real Chromium session uploads through the Next.js proxy, reads library
metadata and retrieves byte-equivalent Unicode/newline source text. This is API
and transport coverage; product upload/reader controls are covered by T34–T39.
Integration tests also cover interrupted workers, retry/cancellation, synthetic
PDF/EPUB inputs and versioned reprocessing. Scanned PDFs are unsupported, and
broader real-book PDF/EPUB fidelity is not established by these fixtures.
Parsed source evidence is not proof of live
narrative extraction, hybrid retrieval or grounded visual reconstruction.

## Grounded reconstruction evaluation — T33

`tests/reconstruction_eval.py` scores stored specifications against every
annotated case of the synthetic corpus. Missing and incorrect inclusions are
kept apart. A canonical trait that matches a fact the case excludes
(temporal, attribution or modality errors), and any cited span beyond the
reading boundary, are **blocking**. Canonical traits matching no annotation
are reported as unannotated extras and are not scored.

| Run | Path | Outcomes | Canonical found | Incorrect | Leaks |
|---|---|---|---|---|---|
| Deterministic regression (`test_reconstruction_integration.py`) | API → PostgreSQL → ideal rule consolidation → gates → stored revision | 16 / 17 | 22 / 23 | 0 | 0 |
| Live (`test_live_reconstruction.py`, 2026-10-21) | Upload → real Dramatiq worker (GLiNER2, fastcoref, appearance cues, EmbeddingGemma) → API → Groq `gpt-oss-120b` consolidation and adjudication → stored revision | 13 / 17 | 14 / 23 | 0 | 0 |

The deterministic run's one miss is the dinner candlelight: "Warm candlelight
lit the room" never names the house, so the attribution gate refuses it. Its
one outcome difference is the journey-attire case, which resolves with an
inferred scar and attire unknown, where the annotation expects insufficient
evidence. Both are pinned.

The live run (ingestion 23 s; 17 requests, about one a minute for Groq's free
8,000 tokens per minute) made 13 consolidation and 9 adjudication calls,
about 87,000 tokens in all. A compose took 2–15 s; consolidations used
3,800–4,300 input and 600–3,200 output tokens, adjudications 760–1,060 input
and 90–210 output. No temporal, spoiler or attribution failure reached a
canonical field. What it lost was recall:

- Four cases came back `insufficient_evidence` where the annotations resolve:
  journey, the chapter-four eye conflict, the house at the return, and the
  compass in childhood. The model either anchored no moment or tied no fact to
  it.
- The war and dinner scars and the sword and compass materials were not
  extracted as canonical at their moments.
- Two unannotated extras appeared: the house "beside ash tree", and "Brann"
  as the sword's holder, which the scorer reads as a value.

Run-to-run variance was visible earlier (T31). These figures are one live
sample on a 14-passage fixture. They are not whole-book recall and not a
quality target. OPEN-05 records them as the first measured baseline, and
PROP-07 proposes targets.

This evidence covers the API and the real pipeline. T39 below separately proves
the browser product flow and retains these broader quality limitations.

## Library browser checks — T34

`apps/web/tests/library.spec.ts` runs through actual sign-in and upload controls
against the isolated API, PostgreSQL, Redis and a Dramatiq ingestion worker.
It checks persisted originals and library reload, empty/other-owner libraries,
safe owner denials, distinct readiness, stale-revision rejection, queued cancel
and retry, malformed-PDF failure/retry, and running cancellation pending worker
confirmation. A stopped worker makes queued state observable; a test-owned parser gate
pauses the real worker before its parse call to exercise pending cancellation.
Latency is controlled by this fixture; parser output is not mocked. One intercepted stale
job read preserves the other tab's old view while mutations still reach the
real API. The unauthenticated form-only check simulates a 401 separately.

The ingestion-only worker intentionally leaves narrative work queued; this is
not proof of extraction quality or the G5 reconstruction/export path. The suite
also checks both themes and horizontal overflow at 320, 768, 1024 and 1440 pixels.
Screenshots remain local. Run the isolated harness as described in
[operations](../operations/development-and-operations.md#library-browser-harness--t34).

## Scoped explorer browser checks — T35

`tests/explorer.spec.ts` uploads the synthetic story through the real browser,
waits for the real worker to publish entities/appearance/search, selects a
boundary and inspects API-derived entity detail. It verifies late alias removal,
clearing abandoned detail and context inputs, explicit ambiguous-identity choices,
narrow layout and a stored request whose entity, moment, scene and cutoff match
the browser selections. The API and PostgreSQL persistence are real; model
adapters are deterministic fixtures, including consolidation and adjudication.
This does not establish live model quality or the complete G5 profile/export path.
Chapter-catalog API tests additionally prove current-parser isolation, safe
metadata, pagination, owner denial and unparsed-source failure.

## Exact source browser checks — T36

`tests/evidence.spec.ts` uses browser uploads and real worker-persisted passages.
A source beginning with accented text, an emoji and a decomposed syllable before
the selected name proves code-point highlight mapping; image-like markup stays
literal text with no image element. A stored specification's attribute resolves
through the real evidence endpoint, selects its exact quote, and source selection
marks the corresponding attribute. A deliberately inaccessible document revision
is sent to the real server: the safe 404 clears the old excerpt. Reducing the
reading boundary clears both inspector and result.

`pnpm --dir apps/web test:spans` additionally checks overlapping Unicode spans and
rejects altered/normalized/out-of-excerpt highlights. Overlap logic is a domain
test; browser checks use the actual persisted spans. The workspace model adapters
remain deterministic; this is source-reader/persistence proof, not live-model
quality evidence.

## Reconstruction workspace browser checks — T37

`tests/visualization.spec.ts` exercises context choices, a stored profile, exact
attribute evidence and a downloaded JSON file that deep-equals the server's
stored specification. It checks canonical, inferred, disputed, unknown and
creative states, interpretation with unchanged canonical traits, insufficient
evidence under an early cutoff, and a deterministic provider-rate-limit failure.
Input/scope changes remove the old profile/export action. This is a real
browser/API/worker/database path with deterministic model adapters; provider
failure is simulated by that adapter, not a live provider outage.

## Revision protocol checks — T38 backend

`test_refinement.py` uses disposable PostgreSQL databases to prove revision
preconditions, cross-owner denial, exact mutation replay, conflicting replay,
immutable historical requests/evidence, canonical locks, prompt conflicts and
body limits. Two concurrent writes at one revision yield one success and one
412. Source, entity, appearance and embedding changes refuse refinement; an old
citation still resolves after the source pointer changes. Guarded migration
round trips exercise 0020/0021 backfill and retain each revision's style/mode.
Downgrading the receipt table intentionally drops idempotency receipts.
These API/database checks are distinct from the browser consumer checks below.

T38's scoped-history API regression verifies that incompatible labels are absent
from list responses and direct/revision reads return 404 under the active scope.
`tests/refinement.spec.ts` adds two real tabs: the first stores a lock/style revision,
the second receives 412, reloads its locks/revision while retaining its style draft,
and then stores the next revision. It revisits revision 1 with its original source,
keeps it read-only and clears it when the boundary narrows. Canonical profiles and
source spans are compared to the original stored result.

## Product acceptance coverage — T39

The deterministic workspace browser suite covers empty/populated libraries,
ambiguous identities and moments, insufficient evidence, safe provider failure,
exact Unicode evidence, exported data and stale two-tab refinement. Its model
adapters are fixtures; its HTTP, PostgreSQL, Redis and worker publication are real.
`tests/accessibility.spec.ts` checks the populated profile/source controls in
light/dark themes, visible text and placeholder contrast, named controls, heading
order, unique IDs, skip-link focus, reduced-motion preference, 320/768/1440-pixel
layouts and 200% text. Enlarged nested panels must retain readable excerpt width
as well as avoid horizontal scrolling. These are targeted Chromium checks, not a
complete WCAG audit, screen-reader assessment or physical-device certification.

`tests/product-flow.spec.ts` is the separate opt-in live browser gate described
in [operations](../operations/development-and-operations.md#library-browser-harness--t34).
It uploads the synthetic story through production bootstraps and requires a
resolved, persisted specification from local extraction/embeddings and Groq.
The browser opens exact evidence and downloads JSON equal to the stored result;
the harness verifies persisted successful provider records, vectors and revisions.
It does not replace T33's broader quality measurement or establish whole-book
recall, throughput, deployment readiness or physical-device coverage.

The 2026-10-22 local live dinner run passed in 47 seconds: source upload through
the production worker, scoped Groq reconstruction, stored profile, exact source
DOM highlight and identical downloaded JSON. The disposable database contained
successful `local` and `groq` records, 14 passage vectors and one saved revision.
An earlier broader "at home after the war" request returned insufficient moment
evidence; this gate uses the source's explicit dinner scene. A separate attempt
returned provider-unavailable safely. The successful run does not remove either
outcome or the previously measured recall limits.

| Requirements | Named evidence and limits |
|---|---|
| REQ-01 | `test_authorization.py`, owner cases in evidence/visualization/refinement/cache integration tests; `library.spec.ts` and scoped history browser checks. Private assets await optional rendering. |
| REQ-02, REQ-04 | Text/PDF/EPUB parsing and source-generation tests, `test_evidence_api.py`; `evidence.spec.ts` exact Unicode DOM spans and `refinement.spec.ts` old revision citations. PDF OCR is excluded. |
| REQ-03 | `test_ingestion_recovery.py`, `test_worker_integration.py`, `library.spec.ts`: queued/running cancellation, retry, stale guards, persisted publication. Narrative-stage retry remains PROP-06. |
| REQ-05–REQ-07 | Entity, chronology, appearance and visual-fact tests; T22 live extraction measurement; explorer identity options. Live extraction retains its measured limitations. |
| REQ-08–REQ-10 | Fusion, semantic/lexical integration, scene/reconstruction tests and T33's deterministic/live scored cases; live recall misses remain recorded above. |
| REQ-11, REQ-12 | Spoiler-eligibility, query-resolution, scoped-cache and history tests; explorer/context/boundary browser cases. |
| REQ-13, REQ-14 | Grounding/adjudication regressions, evidence API and browser source/profile tests distinguish support, conflict, inference and unknowns. |
| REQ-15, REQ-16 | Contracts, stored visualization/refinement integration and browser mode/lock/history/export tests preserve canon and exact portable JSON. |
| REQ-17, REQ-18 | Source-generation, scoped-cache and refinement tests; immutable request/result/lineage frames and dependency/source invalidation. |
| REQ-19 | Upload-limit, provider-contract, bounded-evidence/refinement-body and ingestion-failure tests. Whole-book performance/cost targets and operational drills await Phase 7. |
| REQ-21 | Provider-envelope conformance and deterministic/live adapters exercise role boundaries; optional image adapter awaits Phase 6. |
| REQ-22 | Provider instruction/data separation, hostile-upload limits, wrong-owner grounding rejection and literal source-markup browser rendering. These checks do not prove universal prompt-injection resistance. |
| REQ-20 | Optional image rendering remains Phase 6 and is excluded from G5. |

## Render checks — T40

`test_image_provider.py` drives both DEC-51 adapters (OpenAI and Hugging Face)
against a real local HTTP server: exact route, bearer header and body (prompt
only, no negative prompt); provider-reported token usage; image-type
verification; HTTP refusals, rate limits and OpenAI quota/moderation codes as
definite failures without echoing provider text; 200 responses without a
verifiable image as `PROVIDER_INVALID_OUTPUT`; a sent request without a response
as acceptance unknown; a refused connection as `PROVIDER_UNAVAILABLE`; explicit
opt-in requiring the selected provider's own key.

`test_render_contract.py` exercises real HTTP/PostgreSQL reservations and worker
execution with synthetic image adapters: disabled configuration, raw-prompt
rejection, retained specification/hash, owner isolation, request/cancellation
replay, strong preconditions, concurrent owner-limit enforcement, stale
source/specification/dependencies, the guarded 0021→head downgrade/upgrade, one
provider call under redelivery, private 0600 output with digest and settings,
acceptance-unknown/rejected/storage-failure outcomes that still count toward the
cap, skipped cancelled/unconfigured/changed-model jobs, cancellation during a call
keeping its image, interrupted claims settled without another call (and a held
lock left alone), and a real Redis/Dramatiq worker completing a job whose first
enqueue failed after `dispatch_renders`. The opt-in `test_live_render.py` sends
one bounded request to the named provider; its evidence is recorded with the
task.

`test_render_assets.py` (T41) checks over real HTTP, PostgreSQL and private
storage: exact image bytes with media type, digest ETag, `no-store`, `nosniff`
and inline/attachment filenames; history ordering with the current revision after
a refinement; the reserved snapshot equal to the reopened revision; safe 404s for
another owner, another work and unknown renders; 409 for queued renders, failed
storage after provider acceptance, and stored files that are missing or altered.
`render-history.spec.ts` drives the browser against the real API and a real
Dramatiq worker with a synthetic adapter: render, decoded image, authenticated
download and anonymous 401, the older-specification note after a refinement and
reopening revision 1 without render or refinement controls. Pixel review against
a live provider belongs to T42.

## Real render acceptance — T42

`render-flow.spec.ts` runs the workspace harness (deterministic consolidation of
the synthetic corpus) with the configured image provider and a real Dramatiq
worker. `VISION_TEST_LIVE_RENDER=synthetic` rehearses the flow without billing;
`=1` sends exactly two requests: the canon-first revision 1, then revision 2 with
style "ink wash", interpretation mode and all four canonical facts locked. It
checks both images stored, served and decoded at 1024 px, the replayed
idempotency key returning the first job, two history entries, the older
specification note and an anonymous 401.

Run on 2026-10-22 with OpenAI `gpt-image-1` (low): both succeeded and their
lineage matched revisions 1 and 2. Pixel review found the linen shirt, distinct
people (Élodie and Mira had merged in an earlier single request), no steel armor
and the ink-wash style. It also found contradictions that are not excused: no
left-cheek scar in either image, a roofed house although the roof is missing,
an ambiguous or wrong compass, and a four-panel layout instead of one scene,
induced by the composer's "each shown separately" wording. Locks keep facts in
the prompt; they do not make the image model draw them.

Two approved follow-up requests used `test_live_render.py` with the `compose-v3`
single-scene prompt on revision 1. `gpt-image-1` drew one scene with three distinct
people, the linen shirt and a partly missing roof, but no scar and a wine glass
instead of the compass. `gpt-image-2` drew one scene with three distinct people,
the linen shirt, a roofless ruin beside a large tree and an open brass compass
with a dial; the left-cheek scar was still not visible. Both stored, decoded and
matched their snapshots.

The scar was in every prompt but only as a parenthesised `left cheek:` detail of a
small face in a three-person scene. Two further approved `gpt-image-2` requests
on 2026-10-23 used `compose-v4`. With the subject in the foreground facing the
viewer and the mark as its own first sentence, the scar appeared clearly for the
first time, but on the right cheek: the image's left side. Naming the side as it
appears in the image ("on the right side of the image as Arthur faces the
viewer") put the scar on the left cheek, with the roof gone to bare rafters, the
brass compass in Mira's hands and three distinct people. Both stored, decoded and
matched their snapshots. One correct image is not a rate; side mapping is stated
only for the subject, whose facing the prompt sets.

## Deletion lifecycle — T46

`test_deletion_lifecycle.py` exercises owner/revision/idempotency guards,
immediate absence from every work route, queued cancellation and running-job
coordination, migration downgrade/upgrade, physical original/image removal and
derived-row purge, another book's continued access, interrupted file cleanup,
safe redelivery, and upload replay refusal after physical deletion. Its worker
case uses PostgreSQL, Redis and an actual Dramatiq retention actor.
A delayed database deletion also proves retention can exceed the API's
two-second statement budget without changing the timeout of API connections.
The library browser suite requests deletion through the real API, reloads the
library, observes absence and polls the exact request until cleanup completes.
This proves the API/library lifecycle; no library delete button is implemented.

## Backup and recovery drill — T47

`test_recovery_drill.py` creates actual PostgreSQL dumps with the selected server
image's clients and restores into empty isolated databases/private roots. It
compares exact original, stored specification and image bytes over the API,
checks the other owner's safe `404` and revoked old sessions, replays a deletion
made after the snapshot, refuses occupied/corrupt targets and older deletion
ledgers (including valid-JSON corruption of a deletion's owner), refuses a held worker lease, and proves an interrupted restore remains
unavailable. Queued and running image attempts settle as acceptance unknown
without another adapter call. Interrupted ingestion resumes in a real
Redis/Dramatiq worker with one passage set under redelivery. Probe publication is
recovered into a fresh broker namespace, and a restarted narrative worker reuses
the saved derivation with unchanged entity IDs. These recovery tests use
deterministic model adapters; the packaged drill separately runs pinned local
extraction and embedding models.

`test_render_budget_retention.py` proves that a completed book purge and an
older snapshot cannot reopen an exhausted owner's image budget. It exercises
real reservation APIs with independent valid book specifications, monotonic
post-snapshot usage checkpoints, and migration downgrade/upgrade with retained
receipts and conservatively exhausted legacy purge history. No image provider
call is made by these quota checks.

`make package-check` also backs up actual stopped Compose volumes, makes a later
deletion on the source, restores into a new project/database/volumes, and checks
exact original bytes, owner isolation, revoked sessions and deletion replay
through the restored web proxy. Its printed elapsed time covers this synthetic
drill; it is not a book-length restoration or disaster-recovery target.
`packaged-restore.spec.ts` then signs in through the restored production web
server, checks the surviving library entry and deleted book's absence, opens the
restored entity explorer, and checks a narrow layout and browser errors.

## Local release scope — T48

The intended environment is one Linux machine, loopback web access, locally
provisioned accounts, PostgreSQL 17/pgvector, Redis and one serial worker.
Supported runtimes are the host commands and the packaged Compose stack with
private filesystem storage. DEC-25 excludes external hosting, S3 provisioning
and production acceptance. The application versions, schema and model identities
come from the named commit, lockfiles, image revision labels and stored lineage.

| Requirements | Acceptance evidence |
|---|---|
| REQ-01 | Two-owner API/browser/storage boundaries, revoked sessions, deletion and restore isolation (T07, T41, T43, T46–T47) |
| REQ-02–REQ-04 | Four-format synthetic ingestion, immutable sources, interrupted workers, stable old citations and restored exact excerpts (T10–T16, T36, T47) |
| REQ-05–REQ-07, REQ-09–REQ-10 | Source-linked identities, partial chronology, visual states and temporal/attribution regressions; live recall limits remain recorded in T33 |
| REQ-08 | Lexical/entity/vector retrieval, protected evidence and explicit overflow; measured book-length budgets (T24–T27, T44) |
| REQ-11 | Cutoff/dependency checks before retrieval, consolidation, cache, specification/history and evidence access (T21, T30, T32, T35–T39, T43) |
| REQ-12–REQ-16 | Explicit ambiguity/insufficiency, grounding gates, exact-span reader, locked refinement, portable JSON and persisted browser export (T28–T39) |
| REQ-17–REQ-19, REQ-21 | Versioned role contracts, scoped cache, bounded workers/providers, packaging, deletion and restoration (T17, T25, T32, T40, T43–T47) |
| REQ-20 | Optional specification-only rendering, immutable lineage and private history; live pixels are the T42 evidence, with current synthetic worker/storage/recovery regression |
| REQ-22 | Hostile input, instruction/data separation, literal browser rendering and safe log/error checks (T43) |

The closing local run comprises `make check integration`, the session, library
and workspace browser harnesses, and `make images package-check`. The opt-in
`VISION_TEST_LIVE_WORKSPACE=1` browser gate additionally uses the actual local
models and configured Groq consolidation/adjudication on the synthetic narrative:
upload → processing → stored specification → selected exact source highlight →
JSON download equal to the stored revision. It checks persisted local/Groq model
records, vectors and revisions. It does not request a new paid image.

The final pushed commit must also pass the actual `foundation` CI job before G7
is closed. That job covers static/contracts/build, real database/broker/worker,
session/library/workspace browser and dependency-advisory checks. Packaged images,
real local models and live remote providers retain separate local/opt-in proof;
CI does not silently stand in for those runs. A verified phase and a merged PR
remain separate facts.

Handover retains the T33 model-quality and T42 pixel limitations, the T44 free-tier
context/rate-limit measurements and unaccepted PROP-07/08 proposals. Larger
corpora, full real-book PDF/EPUB fidelity, OCR, broader languages, physical-device
and full screen-reader/WCAG audits, provider-side deletion guarantees, automatic
account deletion/expiry and off-machine disaster recovery are not established.
The [operations guide](../operations/development-and-operations.md) owns startup,
readiness, dispatch, private storage and the rollback/restore procedure. Keep the
source environment intact and stopped until a restored target passes acceptance;
do not process on both at once.
Returning to that untouched source is a rollback only before accepting new user
writes on the target. Afterwards, recover from the current state and latest
deletion ledger into another empty target; do not run an older image against a
newer schema or replace a live database in place.

## OpenAI text evaluation — Q01

DEC-53 adds an opt-in text adapter, not a replacement for the accepted private-book
provider. `test_openai_responses.py` covers the real HTTP wire using a local
synthetic endpoint: strict copied schemas, defaulted fields, bounded tool-free
requests, missing usage, HTTP failures, incomplete/refused responses, retained
charged usage, cancellation, explicit provider selection and effort-dependent
cache/derivation identity. Its PostgreSQL/API case grounds and stores output,
proves cache reuse and separates a changed effort. These tests simulate OpenAI;
the following opt-in measurements use the real provider.

The 2026-10-27 synthetic evaluation used the production local narrative worker,
pinned local embeddings and GPT-6 Luna through the Responses API. The initial
effort comparisons kept the existing 4,096-token consolidation and 2,048-token
adjudication bounds; Q03 separately lifts those bounds in an isolated evaluation.
Every cited span still passed local grounding and reading-boundary checks.

| Variant | Outcomes matching annotations | Canonical found | Incorrect / leaks | Median API-backed query | Reported-token USD estimate |
|---|---|---|---|---|---|
| Historical Groq T33, 2026-10-21 | 13/17 | 14/23 | 0 / 0 | 5.1 s | Not repriced here |
| Luna, low reasoning | 6/17 | 6/23 | 0 / 0 | 39.2 s | $0.02730 |
| Luna, no extra reasoning | 12/17 | 17/23 | 0 / 0 | 20.9 s | $0.01605 |
| Luna, medium reasoning | 6/17 | 4/23 | 0 / 0 | 38.1 s | $0.02909 |
| Luna, low reasoning, native output allowance | 11/17 | 17/23 | 0 / 0 | 31.6 s | $0.02598 |

Low effort exhausted the consolidation output budget nine times; another call
was unavailable. No extra reasoning completed all 22 provider calls without a
budget/refusal failure. It used 29,159 input and 26,268 output tokens across the
17 questions; total query time was 342.2 s, plus 33 s local ingestion. Low used
30,126 input and 48,568 output tokens, with 609.8 s query time. These are
reported-token estimates at standard uncached Luna rates, not invoices; unknown
usage, caching, taxes and future price changes can change billed totals.

The follow-up medium-effort run kept those same token limits and completed all
17 cases in 553.1 s query time plus 21.7 s local ingestion. Nine consolidation
requests exhausted the 4,096-output-token cap; 10 other provider calls succeeded.
Reported usage was 30,042 input and 52,162 output tokens. This is a constrained
configuration result, not a quality comparison with adequate reasoning allowance:
many requests failed before returning a complete answer. No annotated incorrect
canonical claim or spoiler leak was scored; three unannotated extras remain
unscored. A larger-budget medium experiment is separate from this run and has
not been performed. The saved default and limits were not changed.

Q03 retries low effort with Luna's model-native 128,000-output-token ceiling,
a 200,000-total-token guard and a 300-second per-call timeout for consolidation
and adjudication. These are evaluation-only fixture overrides; production limits,
input selection, prompts and saved provider settings are unchanged. A first
attempt exposed an application error: a stored model assumption was dropped
before an inferred trait reached response validation. That interrupted run is
not a completed comparison. A deterministic API regression reproduced the error;
Q03's reason-propagation fix preserves the assumption without making it canonical.

The completed fresh run after that fix had 21 successful provider calls, no token
budget failures and no timeouts. Five calls exceeded 4,096 output tokens; the
maximum was 6,625. It reported 29,121 input and 46,130 output tokens, with 448.1 s
query time plus 28.1 s ingestion. The $0.02598 estimate covers this completed run
only, excluding the interrupted attempt. No annotated incorrect canonical claim
or spoiler leak was scored; three unannotated extras remain unscored. The larger
allowance recovered low effort's capped recall from 6/23 to 17/23, matching the
`none` run's trait count while remaining slower and more expensive. It did not
recover all expected traits or establish real-book reliability. Reports preserve
the capped baseline byte-for-byte and save native limits plus per-call metadata
separately in the ignored measurement directory.

The OpenAI opt-in therefore defaults to `none`; `low` remains selectable for
evaluation. The comparison does not establish that Luna is uniformly better:
canonical recall improved against the historical Groq run, outcome agreement
was lower, and response time was slower. Runs occurred on a shared development
host at different times. Six annotated canonical traits remain missing under
`none`, including unresolved house/Mira/childhood-compass cases and the incomplete
eye-conflict result. No private books or image-generation calls were involved.
The separate ignored reports preserve both variants and the earlier baseline.

The live Chromium product gate also passed with the production API/worker and
Luna `none`: a stored canonical profile, an exact selected source highlight and
JSON export equal to the persisted revision. Database checks found local/OpenAI
run records, 14 vectors and one revision; query usage was 2,504 input and 3,626
output tokens (about $0.00206 at the same uncached rates). No image was requested.
This proves the synthetic browser path, not private-book suitability or faster
responses. The browser proxy was built and checked against the isolated API
before the successful run.
