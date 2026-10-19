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

## Proposed elaborations

These make implementation discussions concrete without pretending the source
documents fixed all details.

| ID | Proposal | Resolve in |
|---|---|---|
| PROP-01 | Zero-based, end-exclusive Unicode code-point offsets against immutable passage text | Ingestion and frontend contract tests; [ingestion](../ingestion/ingestion-contract.md) |
| PROP-02 | Named index generations with explicit publication of compatible completed results | Persistence/job implementation; [operations](../operations/development-and-operations.md) |
| PROP-03 | HTTP outcomes and error envelope described in the API draft | Executable Pydantic/OpenAPI increment |
| PROP-04 | First vertical slice uses a small synthetic TXT/Markdown narrative before format expansion | First implementation increment; [roadmap](implementation-roadmap.md) |
| PROP-05 | Cache identity includes creative mode and locked-fact revision in addition to source/retrieval scope | Reconstruction implementation |

## Open decisions

| ID | Question | Needed before |
|---|---|---|
| OPEN-01 | Authentication/session mechanism and ownership representation | Any network-accessible real upload flow |
| OPEN-02 | Model providers, model IDs, credentials, costs, and source-text handling | Live model integration |
| OPEN-03 | First supported book languages and lexical configurations | Lexical indexing and multilingual claims |
| OPEN-04 | When does carrying an acquired trait forward count as explicit support versus inference? | Temporal reconstruction implementation |
| OPEN-05 | Concrete upload/expansion/time/token/cost/candidate limits and performance targets | Accepting untrusted workloads; then calibrate with measurements |
| OPEN-06 | Runtime versions, package manager, parser format coverage/OCR, embedding dimension and ANN settings | Reproducible development environment |
| OPEN-07 | Revision/edit/retry/idempotency wire protocol, pagination, deletion, and retention | Executable API and persistent lifecycle |
| OPEN-08 | Deployment host, backups, recovery targets, provider retention, and data deletion procedure | External deployment |
| OPEN-09 | Project license, final design tokens, approved logo variants, and exact component selections | Redistribution or public product release |

For OPEN-04, the overview says not to assume permanence from one scene, and the
retrieval example permits carrying a wartime scar forward absent contradiction.
Preserve both observations. Until the rule is settled, label such extrapolation
as inferred when applicability is not established; absence of an end date alone
does not prove persistence.

## Deferred scope

Rendered visuals come after grounded JSON. Voice, animated agent mascots,
microservices, and multi-agent orchestration are not implied by selecting an
agent-interface component source. Production readiness has not been established.

## Changes

Record a changed decision with its reason and affected requirements, contracts,
tests, and data migration. Expensive architecture changes receive a new ADR;
superseded ADRs remain available. Do not reopen the selected retrieval stack as
an A/B comparison without an explicit decision to revisit it.
