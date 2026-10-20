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

Vision is a planned narrative-aware visual reconstruction platform. Ask for a
character as a child, a fortress before a siege, or a family dinner after a war.
Vision is designed to recover the relevant passages, reconstruct the appearance
at that moment, and produce a structured specification for image generation.

## Status

**Local executable foundation; the book pipeline is still being built.**
The repository includes a themed web shell, authenticated API, PostgreSQL/pgvector,
private TXT/Markdown/PDF/EPUB uploads, a durable parser worker with retry and
cancellation, bounded source-evidence reads and generated shared contracts.
Upload/reader screens, narrative extraction and grounded reconstruction are not
available yet. There is no release.
Logo assets are brand material, not product screenshots.

## Run locally

With the [documented prerequisites](docs/operations/development-and-operations.md#local-commands-and-verification):

```sh
make setup
make dev
```

Open `http://127.0.0.1:3000`. Setup generates private local service credentials;
see [operations](docs/operations/development-and-operations.md) for account setup,
verification commands and shutdown. Vision runs locally; LLM integration will use
the installed FreeLLM API gateway.

## Planned capabilities

- Explore characters, places, objects, and their contextual appearances.
- Keep identity, changes over time, and scene-specific details separate.
- Inspect source evidence behind each canonical visual attribute.
- Respect reading boundaries, including descriptions revealed in later flashbacks.
- Export provider-independent visual JSON, with optional image rendering later.

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
