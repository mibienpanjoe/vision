# Documentation map

**Status:** executable local foundation and checked synthetic corpus, 2026-10-19.
TXT, Markdown, PDF (no OCR) and EPUB ingestion with retry/cancellation and
bounded evidence reads are implemented; narrative reconstruction remains planned.

The structure follows FIRA's separation of product scope, domain contracts,
canonical data, operations, and architecture decisions. FIRA's financial domain,
roles, delivery deadlines, and branch model do not apply to Vision.

## Recommended reading order

| Order | Owning document | What it answers |
|---|---|---|
| 1 | [Project overview](product/project-overview.md) | What Vision is intended to do |
| 2 | [Requirements and acceptance](product/requirements-and-acceptance.md) | What must be true for each capability |
| 3 | [Decision register](product/decision-register.md) | What is selected, proposed, open, or deferred |
| 4 | [Canonical model](data/canonical-model.md) | What the domain objects mean and how they relate |
| 5 | [Narrative contract](narrative/narrative-contract.md) | How identity, chronology, facts, and ambiguity behave |
| 6 | [Ingestion contract](ingestion/ingestion-contract.md) | How sources become versioned, inspectable evidence |
| 7 | [Retrieval strategy](architecture/retrieval-strategy.md) | The adopted retrieval and reconstruction pipeline |
| 8 | [Visual specification](visualization/visual-specification.md) | What a trustworthy output contains |
| 9 | [System architecture](architecture/system-architecture.md) | Components, ownership, and allowed dependencies |
| 10 | [API contract](api/api-contract.md) | Implemented foundation routes and proposed product resources |
| 11 | [Acceptance strategy](testing/acceptance-strategy.md) | How the intended behavior will be proved |
| 12 | [Implementation roadmap](product/implementation-roadmap.md) | The build order and completion gates |

Supporting owners:

- [Development and operations](operations/development-and-operations.md): current
  local setup, runtime topology, job visibility, and remaining operational gates.
- [Visual identity](design/visual-identity.md): logo direction, component sources,
  asset inventory, and proposed export targets.
- [ADR-0001](adr/0001-modular-monolith.md): backend and persistence baseline.
- [ADR-0002](adr/0002-temporal-hybrid-retrieval.md): retrieval rationale and exclusions.
- [Contributing](../CONTRIBUTING.md): workflow and documentation maintenance.
- [Security](../SECURITY.md): trust, ownership, uploads, providers, and secrets.

## Authority and status

The project overview belongs under `docs/product/`; the detailed retrieval
strategy belongs under `docs/architecture/`. Both remain useful source
specifications and are maintained in those locations, without root duplicates.
Focused contracts own the elaborated requirements. None establish runtime proof.
Later maintainer decisions are recorded in the register and reflected in the
affected specifications.

The design document owns the approved logo and selected typography, light/dark
themes, and component direction. The overview links to those choices rather
than maintaining a second palette or font list. Asset approval and selected
design tokens do not imply a rendered or accessibility-tested application.

Use these labels consistently:

- **Baseline:** already selected in the source documents or explicitly by the maintainer.
- **Proposed:** a concrete elaboration awaiting implementation-level resolution.
- **Open:** no choice has been made.
- **Deferred:** intentionally outside the current delivery increment.
- **Verified:** a named check actually ran on the current artifact or application.

Do not maintain a second copy of the detailed retrieval algorithm, security
policy, setup procedure, or acceptance matrix on another page.
