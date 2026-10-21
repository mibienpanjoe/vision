# Acceptance and verification strategy

**Status:** corpus, local foundation and TXT/Markdown upload → parser → authorized
evidence checks are implemented; the provider envelope has deterministic
contract tests (T17); entity, event and visual-fact derivation, ambiguity,
chronology, modality, attribution gates, conflicts and cutoff-filtered browse
have deterministic fixture, PostgreSQL and API evidence (T18–T21). Live
extraction quality and the remaining scenarios below remain pending.
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
were reviewed against the story; automated narrative extraction and reconstructed
outputs have not been evaluated. T06/T36 must still prove executable client
contracts and DOM highlighting.

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

The foundation checks establish database readiness/migrations, authenticated
ownership/session boundaries, real broker/worker probe execution, shared contracts
and the browser shell/font/icon/session surfaces. Commands and isolated fixture
setup belong to [operations](../operations/development-and-operations.md#local-commands-and-verification).
They do not establish ingestion, extraction/retrieval quality, narrative temporal
correctness, rendered images or full product security. The synthetic oracle is
still the expected input to those later evaluations. Check the actual CI run for
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
and transport coverage; product upload/reader controls are still planned.

Broader worker interruption/retry/cancellation, PDF/EPUB adapters and reprocessing
remain separate acceptance tasks. Parsed source evidence is not proof of live
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

This evidence covers the API and the real pipeline. A browser product flow is
Phase 5.

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
