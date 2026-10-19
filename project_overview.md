# vision — project overview

> **Read the words. See the world.**

**Status:** product and technical definition  
**Product:** Vision  
**Category:** narrative-aware visual reconstruction platform  
**Primary output:** source-grounded, structured JSON specifications for image generation

## 1. Product definition

Vision is a platform that turns books and narrative documents into visualizable worlds. Users upload a work, explore its characters, locations, objects, and scenes, and ask Vision to describe how a subject should look **at a particular moment and in a particular context**. Vision recovers relevant evidence from the original text, reconstructs a coherent visual state, and produces a validated JSON prompt for an image-generation system.

Vision is **not** a generic “chat with a PDF” interface, a one-paragraph-to-image converter, or a prompt generator that freely invents missing facts. Its core asset is a **source-linked narrative world model**: entities, aliases, attributes, events, relationships, changes over time, and the passages supporting each claim.

### Product promise

- **Faithfulness:** preserve what the author actually describes; separate explicit detail, defensible inference, and creative completion.
- **Temporal and situational accuracy:** distinguish a character as a child, at war, or at home; distinguish a place before and after an event.
- **World coherence:** account for period, materials, climate, culture, environment, narrative atmosphere, and style.
- **Traceability:** show which passage supports each visual attribute; make uncertainty and conflict visible.
- **Portable output:** return provider-independent structured JSON plus an image-model-ready prompt.

## 2. Core use cases

1. **Characters:** “Show Arthur as a child,” “Arthur returning home after the war,” or “What does Arthur look like in chapter 14?”
2. **Places:** “Reconstruct the Northern Keep before the siege,” “What does the protagonist’s house look like at night?”
3. **Objects:** “Visualize the sword described in the coronation scene.”
4. **Scenes:** “Reconstruct the family dinner after Arthur returns,” preserving who is present, where they are, and what the text establishes.
5. **Exploration:** browse known characters, places, and contextual appearances; inspect evidence and request a different interpretation.

Queries may name chapters, story events, ages, locations, clothing, or circumstances. Vision should infer the intended time/context when justified. If a broad query maps to materially different appearances, it should offer meaningful variants rather than silently blend them.

## 3. Core domain principles

### 3.1 Identity ≠ state ≠ context

- **Identity:** an enduring entity with names, aliases, relationships, and identifying traits.
- **State:** an appearance or property valid during some story interval (age, injuries, aging, building damage).
- **Context:** a specific scene/situation (armor in battle, casual clothes at home, lighting and weather).

An acquired scar can persist; battle armor usually does not. Features are never assumed permanent simply because they appear in one passage.

### 3.2 Story chronology ≠ document order

A later chapter can be a flashback, dream, rumor, or retrospective narration. Store both **source position** (chapter/page/offset) and **story-time placement** (event, age, relative chronology, interval), allowing partial order and unknown dates. Do not infer chronology from chapter order alone.

### 3.3 Evidence comes before aesthetics

Build a factual visual profile first, then compose an artistic prompt. Never let stylistic completion rewrite canonical facts. Track perspective (who describes the detail), modality (fact, dream, rumor, metaphor), conflicts, and unresolved unknowns.

### 3.4 Two creative modes

- **Canon-first:** only grounded details presented as canonical; necessary image-model defaults disclosed as creative choices.
- **Creative interpretation:** add plausible world-consistent details, explicitly tagged as creative rather than attributed to the author.

### 3.5 Spoiler awareness

Provide a **whole-book** mode and a **read-through-chapter** boundary. Evidence, extracted facts, events, and visual results must obey the selected reading boundary; a childhood flashback in a later chapter should not be exposed prematurely.

## 4. Product capabilities

### Book library and ingestion

- Upload PDF, EPUB, TXT, and Markdown initially; retain the original file privately.
- Parse and preserve chapter/section structure, passage offsets, source page references where available, and stable passage identifiers.
- Run asynchronous ingestion, indexing, entity linking, and narrative extraction; report progress and errors.
- Allow document reprocessing when extraction or indexing versions change.

### Narrative understanding

- Identify characters, places, objects, their aliases, and relationships.
- Extract evidence-backed appearance claims, scene descriptions, and event/temporal signals.
- Resolve co-reference and distinguish subject/object attribution (“his armor” vs someone else's).
- Represent uncertainty, contradiction, narrator perspective, persistent changes, and scene-specific attributes.
- Store a compact, reusable world model **without replacing the original passages**.

### Visual exploration and generation

- Natural-language queries with optional entity, story event, chapter boundary, and style controls.
- Context selector for entities with distinct valid appearances (childhood / battle / home / later life).
- Structured profile showing source-backed attributes and unknowns.
- JSON prompt generation, validation, copy/export, and history of generations.
- Source panel: click an attribute to inspect its actual supporting excerpt.
- Optional direct image-generation adapter after JSON composition; generated images are artifacts, not evidence.
- Prompt refinement must preserve locked canonical facts unless the user explicitly selects creative reinterpretation.

## 5. End-to-end workflow

```text
Upload book
  → parse + chapter/scene segmentation + source mapping
  → entity/alias resolution + event and appearance extraction
  → store passages, searchable indexes, and narrative world model

User asks to visualize a subject
  → parse intent, entity, time, context, spoiler boundary
  → retrieve entity-linked facts + lexical and semantic passages
  → rerank and consolidate evidence; verify source claims
  → reconstruct temporally valid appearance and world setting
  → generate provider-independent visual specification
  → validate JSON and attribute-level grounding
  → show prompt, evidence, unknowns and optional image
```

Retrieval is specified in detail in [`retrieval_strategy.md`](./retrieval_strategy.md).

## 6. Technology stack

| Layer | Chosen technology | Responsibility |
|---|---|---|
| Web application | Next.js + TypeScript | Library, exploration workspace, visual outputs |
| UI system | Tailwind CSS + shadcn/ui | Accessible, consistent components |
| Backend API | Python + FastAPI | REST API, domain orchestration, generation contracts |
| Schemas | Pydantic + JSON Schema | Typed payloads and strict model outputs |
| Database | PostgreSQL | Books, passages, entities, facts, events, provenance |
| Lexical retrieval | PostgreSQL full-text search | Exact names, aliases, phrases and descriptions |
| Semantic retrieval | pgvector in PostgreSQL | Related expressions and unnamed descriptions |
| Parsing | Docling + format-specific adapters | Ingest PDF/EPUB/TXT/Markdown; retain location metadata |
| Model integrations | Provider adapter interfaces | Extraction, reasoning, embeddings, reranking, image generation |
| Background work | Redis + Dramatiq | Ingestion and re-indexing jobs |
| File storage | Local filesystem in development; S3-compatible object storage in deployment | Originals, derived assets, optional images |
| ORM/migrations | SQLAlchemy + Alembic | Models and schema evolution |
| Testing | pytest; Playwright | Extraction, API, end-to-end product tests |
| Infrastructure | Docker Compose | Local development and deployment baseline |

**Explicitly excluded from the baseline:** PageIndex, a dedicated graph database, a multi-agent orchestration framework, and separate vector/search infrastructure. PostgreSQL supplies the necessary entity, temporal, lexical, and vector capabilities with fewer moving parts.

### AI model roles

Keep models interchangeable behind narrow adapters rather than hard-coding a provider:

- **Extraction model:** identify entities, aliases, appearances, event signals, source spans.
- **Reasoning model:** resolve context and chronology, consolidate evidence, assemble grounded visual profiles.
- **Embedding model:** index and retrieve semantically related passages.
- **Reranker:** distinguish genuinely useful passages from superficially similar text.
- **Optional image model:** render images from validated specifications.

Use structured output validation and explicit source-span checks; an LLM confidence statement is not a substitute for verified evidence.

## 7. Data model

Core tables/collections:

- `works`, `documents`, `chapters`, `scenes`, `passages`: source hierarchy and stable offsets.
- `entities`, `entity_aliases`, `entity_mentions`, `entity_relations`: identity and co-reference.
- `events`, `event_relations`, `temporal_anchors`: story chronology and partial order.
- `visual_facts`, `fact_evidence`, `fact_conflicts`: scoped appearance claims, support, contradictions.
- `appearance_states`: cached reconstructions for entity + story-time + context + reading boundary.
- `visualizations`, `visualization_evidence`, `assets`: outputs, revisions, source references, optional images.
- `ingestion_jobs`, `model_runs`: operational visibility, reproducibility, extraction versions.

A visual fact should include at least: `entity_id`, `attribute`, `value`, `scope` (persistent/interval/scene), `event_id` or temporal relation, `context`, `evidence_passage_id`, `evidence_span`, `support_type` (explicit/inferred/creative), `perspective`, and `certainty/ambiguity metadata`.

Use relational structure for identity, provenance and event links; JSONB is appropriate for flexible visual attributes and generation specifications. Don't force a fully ordered chronology when the book doesn't establish one.

## 8. Product/API contracts

Illustrative endpoints (subject to versioning):

```text
POST   /v1/works                 upload work
GET    /v1/works                 library
GET    /v1/works/{id}            ingestion and metadata
GET    /v1/works/{id}/entities   browse characters, places, objects
GET    /v1/entities/{id}/contexts available appearances/periods
POST   /v1/visualizations        resolve query, construct prompt
GET    /v1/visualizations/{id}   JSON, profile and evidence
POST   /v1/visualizations/{id}/render  optional image rendering
```

Example abbreviated output:

```json
{
  "schema_version": "1.0",
  "subject": {"entity_id": "arthur", "type": "character"},
  "scope": {"story_event": "return_home", "reading_cutoff": "whole_book"},
  "visual_profile": {
    "persistent": [{"attribute": "scar", "value": "left cheek", "source_ids": ["p-241"]}],
    "contextual": [{"attribute": "clothing", "value": "linen tunic", "source_ids": ["p-592"]}]
  },
  "world_context": {"setting": "stone farmhouse", "mood": "quiet, relieved"},
  "unknowns": ["precise_height"],
  "creative_additions": [],
  "generation": {"prompt": "...", "aspect_ratio": "2:3", "style": "cinematic realism"},
  "evidence": [
    {"source_id": "p-241", "support": "explicit"},
    {"source_id": "p-592", "support": "explicit"}
  ]
}
```

Actual `source_ids` must resolve to stored spans. For real outputs, also record model/index versions and unresolved conflicts.

## 9. Project structure

```text
vision/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── library/
│   │   │   ├── reader/
│   │   │   ├── world-explorer/
│   │   │   └── visualization/
│   │   └── lib/
│   └── api/
│       ├── app/
│       │   ├── api/v1/
│       │   ├── core/
│       │   ├── db/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   │   ├── ingestion/
│       │   │   ├── narrative/       # entities, events, temporal facts
│       │   │   ├── retrieval/       # FTS, vector, fusion, reranking
│       │   │   ├── reconstruction/  # contextual appearance states
│       │   │   ├── verification/    # evidence checking
│       │   │   └── visualization/   # profile and JSON composition
│       │   ├── providers/           # AI adapters
│       │   └── workers/
│       ├── migrations/
│       └── tests/
├── packages/
│   └── contracts/                 # shared generated TS types / JSON schema
├── docs/
│   ├── project_overview.md
│   ├── retrieval_strategy.md
│   └── architecture-decisions/
├── infrastructure/
│   └── docker/
├── docker-compose.yml
├── .env.example
└── README.md
```

Keep a **modular monolith** in the FastAPI application. Separate domain services and adapters, not microservices. Generate TypeScript interfaces from versioned JSON Schema/OpenAPI rather than hand-maintaining duplicate contracts.

## 10. Visual identity and UX direction

### Design concept

**Editorial minimalism × cinematic workspace.** Vision should feel like a **literary observatory**—quiet, intelligent, immersive and precise. The interface stays neutral; the book and its generated visuals carry the atmosphere.

Reference principles: Readwise Reader's reading ergonomics, Linear's information density and interactions, and an editorial publication's visual hierarchy. These are inspiration, not templates to copy.

### Palette

| Token | Color | Usage |
|---|---|---|
| Canvas | `#F8F7F4` | Warm light background |
| Surface | `#FFFFFF` | Cards and panels |
| Ink | `#242424` | Main text |
| Muted | `#817D76` | Secondary labels |
| Accent | `#A28B71` | Sparse active-state emphasis |
| Cinema | `#252527` | Optional immersive dark viewer |

Use accessible contrast for text and controls; don't use low-contrast accent text on white. Provide dark-mode surfaces and token mappings rather than hard-coded colors in components.

### Typography

- **Interface:** Geist or Inter.
- **Editorial headings:** Instrument Serif.
- **Book passages:** Source Serif 4.
- **Structured JSON:** Geist Mono.

### Primary screens

1. **Library:** book covers, ingestion status, recently explored worlds; spacious, warm, editorial.
2. **Book workspace:** left navigation (entities, places, scenes, time); central visualization canvas/query; right evidence and attributes inspector. On narrow screens, drawers/tabs replace simultaneous columns.
3. **Visualization detail:** large artwork or preview, context/time selector, grounded attribute breakdown, side-by-side citations, editable creative settings, JSON export.
4. **Source reader:** original paragraphs and chapter references, highlight exact spans behind a visual attribute.

### Interaction rules

- An attribute click opens its underlying evidence; a passage click highlights the corresponding attributes.
- Temporal variants are selectable by human-readable context (childhood, war, at home), not only numeric chapter.
- Make **explicit / inferred / creative / disputed** visible without crowding the main canvas.
- Support keyboard search and sensible loading states for lengthy extraction.
- Use restrained motion and image reveals. Avoid neon “AI” effects, heavy glassmorphism, gimmicky fantasy motifs, and visual clutter.
- Provide an immersive dark canvas for generated art while keeping research/evidence accessible.

## 11. Operational and trust requirements

- Keep uploads private by default; enforce work ownership/access boundaries.
- Protect copyrighted source text; avoid publicly exposing whole book contents. Provide short cited excerpts within an authorized user's workspace.
- Redact secrets and treat uploaded documents as untrusted instructions; document text must not control system prompts or tool access.
- Record ingestion, extraction, retrieval and prompt versions for reproducibility.
- Fail visibly when parsing is incomplete, chronology cannot be resolved, or evidence is insufficient.
- Set resource limits on uploads, model calls, and image generation; provide cancellation and retry for jobs.

## 12. Build sequence

This is an **implementation order, not a reason to omit essential quality mechanisms**.

1. **Narrative representation:** ingestion with reliable offsets; entities, aliases, events, appearance facts, chronology, and provenance.
2. **Retrieval and reconstruction:** combined lexical/vector/entity retrieval, temporal filtering, reranking, contradiction handling, verification, strict JSON.
3. **Product experience:** library, contextual workspace, evidence inspector, time/scene variants, prompt export.
4. **Rendered visuals:** image-provider adapter, generation history, creative refinement and consistent references.
5. **Operational hardening:** permission boundaries, observability, reprocessing/versioning, resilience and performance.

### Definition of a trustworthy result

A visualization is ready only when it has: a resolved subject; an explicit time/context or clearly stated ambiguity; source-backed facts; no known incompatible attributes; clearly separated inferred/creative choices; valid JSON; and inspectable provenance.

---

**Companion architecture:** [`retrieval_strategy.md`](./retrieval_strategy.md) defines the retrieval design selected for Vision, including indexing, evidence collection, temporal reconstruction, and verification.
