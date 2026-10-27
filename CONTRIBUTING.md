# Contributing to Vision

Vision implements a local book-ingestion, grounded reconstruction and optional
rendering workspace, with private storage and recovery. Start with the
[documentation map](docs/documentation-map.md), then the owning specification for
the area you are changing. The roadmap distinguishes the target product from
delivered capabilities.

## Working conventions

1. Identify the requirement and a small, reviewable outcome.
2. Use the existing domain contract. Record missing choices as proposals rather
   than silently changing accepted decisions.
3. Update the owning specification and affected summaries in the same change.
4. Verify the changed artifact and report what actually ran.
5. Commit a coherent increment using `docs:`, `feat:`, `fix:`, `test:`, `refactor:`,
   or `chore:`. Push or open a pull request when requested by the maintainer.

Application changes should normally use short branches from `main`.
There is no inherited FIRA `develop` branch or multi-role workflow. Do not rewrite
published history without explicit authorization.

## Documentation authority

The [decision register](docs/product/decision-register.md) distinguishes baseline
decisions, proposals, and unresolved questions. An accepted design is not an
implemented capability. Significant architectural changes need an ADR with
context, consequences, and any migration effect. Preserve superseded decisions
and link their replacements.

Keep each topic on its owning page. Use links instead of copying procedures,
requirements, or contracts. Keep the overview under `docs/product/` and the
retrieval strategy under `docs/architecture/`; update the owning specifications
and register when a later decision qualifies the brief.

## Verification and completion

For documentation, check relative links and anchors, Markdown fences, embedded
JSON examples, requirement references, status labels, and unintended changes to
source material. For images, inspect the actual output and record its origin.
The corpus checks and their command are documented in the
[acceptance strategy](docs/testing/acceptance-strategy.md). Local checks and CI
cover the executable foundation. The
[operations guide](docs/operations/development-and-operations.md) owns setup
and verification commands.

For code changes, demonstrate the affected path using the
[acceptance strategy](docs/testing/acceptance-strategy.md). A mock establishes a
simulated result; integration claims require real persistence and provider or
worker behavior. A feature crossing frontend and backend boundaries also needs
a browser check of its visible result.

Keep `tasks/`, `.local/`, credentials, private books, and runtime artifacts out of
commits. Use synthetic narrative fixtures or appropriately licensed test texts;
record their provenance. Check third-party component notices before copying
source. No license is granted by the absence of a project license file.
