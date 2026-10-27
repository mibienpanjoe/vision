<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/vision-mark-dark-tile.png" />
    <img src="assets/brand/vision-mark.png" width="96" height="96" alt="Vision: an open book forming an illuminated doorway" />
  </picture>
</p>

<h1 align="center">Vision</h1>

<p align="center">
  <strong>Read the words. See the world.</strong><br />
  Reconstruct characters, places, objects, and scenes from books using source-linked visual evidence.
</p>

<p align="center">
  <a href="docs/documentation-map.md"><strong>Read the documentation</strong></a>
  · <a href="docs/product/requirements-and-acceptance.md">Product scope</a>
  · <a href="CONTRIBUTING.md">Contributing</a>
</p>

Vision is a local narrative-aware visual reconstruction workspace. Ask for a
character as a child, a fortress before a siege, or a family dinner after a war.
Vision recovers the relevant passages, reconstructs the appearance
at that moment, and produce a structured specification for image generation.

## Status

**Implemented for local use; final acceptance is tracked in the documentation.**
Upload TXT, Markdown, text-layer PDF or EPUB, explore entities within a reading
boundary, inspect exact source spans, and create, refine and export grounded
visual specifications. Optional image rendering retains private assets and
specification history. Local packaging, book deletion through the API (no library
delete button yet) and backup/restoration are implemented. See the
[acceptance scope and measured limits](docs/testing/acceptance-strategy.md)
before treating model output as complete or images as faithful to every detail.
No hosted service or production release is claimed.

## Run locally

With the [documented prerequisites](docs/operations/development-and-operations.md#local-commands-and-verification):

```sh
make setup
make dev
```

Open `http://127.0.0.1:3000`. Setup generates private local service credentials;
see [operations](docs/operations/development-and-operations.md) for account setup,
verification commands and shutdown. Ingestion and embeddings run locally;
query-time consolidation uses configured Groq access. Image rendering requires
separate provider configuration. The [operations guide](docs/operations/development-and-operations.md)
owns model setup, private storage and recovery.

## Capabilities

- Explore characters, places, objects, and their contextual appearances.
- Keep identity, changes over time, and scene-specific details separate.
- Inspect source evidence behind each canonical visual attribute.
- Respect reading boundaries, including descriptions revealed in later flashbacks.
- Export provider-independent visual JSON and optionally render a validated revision.

## Start here

Read the [documentation map](docs/documentation-map.md) for the recommended order
and the owner of each topic. The [project overview](docs/product/project-overview.md)
and [retrieval strategy](docs/architecture/retrieval-strategy.md) are organized
under product and architecture documentation.

The selected baseline combines **Next.js and TypeScript**, **FastAPI**, and
**PostgreSQL with full-text search and pgvector**. Redis and Dramatiq handle
background ingestion; model integrations sit behind provider adapters.
See the [architecture](docs/architecture/system-architecture.md).

The interface will use shadcn/ui with selected components from agent-interface
libraries such as [Agents Kit](https://github.com/agents-ui/agents-kit).
The [visual identity](docs/design/visual-identity.md) pairs the approved
book-and-doorway logo with warm paper, charcoal, and gold themes. Inter handles
controls, Source Serif 4 handles literary text, and Geist Mono handles JSON.

## Contributing and licensing

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for documentation and future development
work, and [SECURITY.md](SECURITY.md) for uploads, evidence, and secrets.
No project license has been selected. Third-party components retain their own
license and attribution requirements.
