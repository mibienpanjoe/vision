# ADR-0001 — Modular backend and shared PostgreSQL baseline

**Status:** accepted baseline, implementation pending.
**Recorded:** 2026-10-19.
**Source:** project overview §§6–9; this records an existing choice.

## Context

Identity, chronology, evidence, scoped reconstruction, and output lineage share
closely related data. The project has not started implementation and does not
need the operational burden of independently deployed domain services.

## Decision

Use a FastAPI modular monolith with explicit ingestion, narrative, retrieval,
reconstruction, verification, visualization, and provider boundaries. Next.js
and TypeScript supply the web application. PostgreSQL supplies relational data,
JSONB, full-text search, and pgvector. SQLAlchemy and Alembic own persistence
and migration evolution; Pydantic/JSON Schema/OpenAPI own typed interfaces.

Redis and Dramatiq are selected for background work. Workers execute the same
domain services as the API; they are execution roles, not separate domain
microservices. Keep private files local in development and use S3-compatible
storage in deployment. Docker Compose is the intended local baseline.

## Alternatives and exclusions

The source baseline excludes microservices, dedicated graph infrastructure,
separate search/vector services, and multi-agent orchestration. FIRA's optional
inline execution design is not inherited: Vision explicitly selects background
ingestion with Redis and Dramatiq.

## Consequences

Ownership and provenance are easier to enforce in one relational system;
modularity still needs service contracts and review. Workers, object storage,
and external providers require durable retries and cross-system recovery.
Runtime versions, deployment host, authorization implementation, and capacity
remain open; this ADR does not claim that those integrations exist.

Revisit service separation or additional search infrastructure only with
measured requirements and an explicit migration/compatibility decision.
