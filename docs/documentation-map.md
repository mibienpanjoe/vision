# Documentation map

**Status:** working definition, 2026-10-19. No application has been implemented.

The structure follows FIRA's separation of product scope, domain contracts,
canonical data, operations, and architecture decisions. FIRA's financial domain,
roles, delivery deadlines, and branch model do not apply to Vision.

## Recommended reading order

| Order | Owning document | What it answers |
|---|---|---|
| 1 | [Project overview](../project_overview.md) | What Vision is intended to do |
| 2 | [Requirements and acceptance](product/requirements-and-acceptance.md) | What must be true for each capability |
| 3 | [Decision register](product/decision-register.md) | What is selected, proposed, open, or deferred |
| 4 | [Canonical model](data/canonical-model.md) | What the domain objects mean and how they relate |
| 5 | [Narrative contract](narrative/narrative-contract.md) | How identity, chronology, facts, and ambiguity behave |
| 6 | [Ingestion contract](ingestion/ingestion-contract.md) | How sources become versioned, inspectable evidence |
| 7 | [Retrieval strategy](../retrieval_strategy.md) | The adopted retrieval and reconstruction pipeline |
| 8 | [Visual specification](visualization/visual-specification.md) | What a trustworthy output contains |
| 9 | [System architecture](architecture/system-architecture.md) | Components, ownership, and allowed dependencies |
| 10 | [API contract](api/api-contract.md) | Proposed HTTP resources and unresolved wire details |
| 11 | [Acceptance strategy](testing/acceptance-strategy.md) | How the intended behavior will be proved |
| 12 | [Implementation roadmap](product/implementation-roadmap.md) | The build order and completion gates |

Supporting owners:

- [Development and operations](operations/development-and-operations.md): current
  setup status, future runtime topology, job visibility, and deployment gates.
- [Visual identity](design/visual-identity.md): logo direction, component sources,
  asset inventory, and proposed export targets.
- [ADR-0001](adr/0001-modular-monolith.md): backend and persistence baseline.
- [ADR-0002](adr/0002-temporal-hybrid-retrieval.md): retrieval rationale and exclusions.
- [Contributing](../CONTRIBUTING.md): workflow and documentation maintenance.
- [Security](../SECURITY.md): trust, ownership, uploads, providers, and secrets.

## Authority and status

The root `project_overview.md` and `retrieval_strategy.md` are retained unchanged
as source material. Focused specifications organize their requirements; they do
not establish runtime proof. Later explicit maintainer decisions are recorded
in the register and take precedence where they qualify the source brief.

The overview's section 10 is initial UX and styling input. The design document
owns the current visual direction: shadcn/ui, selected agent-interface
components, and the supplied logo. Exact design tokens and final asset approval
remain distinct from that direction.

Use these labels consistently:

- **Baseline:** already selected in the source documents or explicitly by the maintainer.
- **Proposed:** a concrete elaboration awaiting implementation-level resolution.
- **Open:** no choice has been made.
- **Deferred:** intentionally outside the current delivery increment.
- **Verified:** a named check actually ran on the current artifact or application.

Do not maintain a second copy of the detailed retrieval algorithm, security
policy, setup procedure, or acceptance matrix on another page.
