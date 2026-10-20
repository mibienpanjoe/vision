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
| DEC-16 | Inter for UI, Source Serif 4 for literary text/headings, Geist Mono for structured output; warm paper/charcoal/gold light and dark themes | Selected under maintainer delegation, 2026-10-19; [visual identity](../design/visual-identity.md) |
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

## Proposed elaborations

These make implementation discussions concrete without pretending the source
documents fixed all details.

| ID | Proposal | Resolve in |
|---|---|---|
| PROP-04 | First vertical slice uses a small synthetic TXT/Markdown narrative before format expansion | First implementation increment; [roadmap](implementation-roadmap.md) |
| PROP-05 | Cache identity includes creative mode and locked-fact revision in addition to source/retrieval scope | Reconstruction implementation |

## Open decisions

| ID | Question | Needed before |
|---|---|---|
| OPEN-01 | Resolved by DEC-26; later work consumes the validated ActorScope | Any network-accessible real upload flow |
| OPEN-02 | Gateway selected by DEC-24; role/model capabilities, credentials, budgets and source handling remain to verify | Live model integration |
| OPEN-03 | First language resolved by DEC-22 (English); broader languages/configurations remain open | Lexical indexing and multilingual claims |
| OPEN-04 | Resolved for the first slice by DEC-22; revisit only with an explicit changed decision | Temporal reconstruction implementation |
| OPEN-05 | Concrete upload/expansion/time/token/cost/candidate limits and performance targets | Accepting untrusted workloads; then calibrate with measurements |
| OPEN-06 | Runtime/package choices resolved by DEC-19 and PDF parsing by DEC-28; OCR coverage, embedding dimension and ANN settings remain open | Reproducible development environment |
| OPEN-07 | Shared revision/idempotency resolved by DEC-23; route payloads, pagination, deletion and retention remain open | Executable API and persistent lifecycle |
| OPEN-08 | External deployment excluded by DEC-25; local recovery, retention and deletion remain required | External deployment |
| OPEN-09 | Project license, exact component selections, final wordmark/vector assets, and any future optically simplified favicon | Redistribution or relevant implementation increment |

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
