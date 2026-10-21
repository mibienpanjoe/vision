"""Local passage vectors (the `index` stage) and scoped similarity candidates.

A query is answered only from an index derivation built by the same embedder
version, so vectors from different models or dimensions never meet. Candidates
are restricted to the plan's document, parser revision and reading boundary in
SQL before they are returned. Similarity orders candidates; it is never evidence.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.models.embeddings import DIMENSION, PassageEmbedding
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.providers.embeddings import Embedder
from app.services.narrative.derivations import claim
from app.services.retrieval.evidence import Candidate
from app.services.retrieval.lexical import in_scope, terms
from sqlalchemy import func, select
from sqlalchemy.orm import Session

STAGE = "index"
LIMIT = 50
ASPECTS = {
    "character": ["the appearance of {label}: face, hair, eyes, skin and build",
                  "what {label} wore: clothes, armour, accessories and things carried"],
    "place": ["what {label} looked like: buildings, rooms, roof, walls and surroundings",
              "the light, weather and atmosphere at {label}"],
    "object": ["what {label} looked like: material, colour, size and shape"],
    "organization": ["the look of {label}: uniforms, emblems, banners and places"],
}


def index_version(embedder: Embedder) -> str:
    return f"index-v1/{embedder.provider}/{embedder.model}/d{embedder.dimension}"[:160]


def index_passages(engine, generation_id: uuid.UUID, embedder: Embedder,
                   cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    if embedder.dimension != DIMENSION:
        raise ValueError("Embedder dimension does not match the passage index")
    derivation_id, attempt, _, passages = claim(engine, generation_id, STAGE, index_version(embedder), None)
    if attempt is None:
        return derivation_id
    vectors = embedder.documents([p.text for p in passages])
    with Session(engine) as db, db.begin():
        derivation = db.scalar(select(Derivation).where(Derivation.id == derivation_id).with_for_update())
        if derivation.attempt != attempt or derivation.status != "running":
            return derivation_id
        if cancelled():
            derivation.status, derivation.completed_at = "cancelled", datetime.now(UTC)
            return derivation_id
        db.add_all(PassageEmbedding(derivation_id=derivation_id, passage_id=p.id, embedding=v)
                   for p, v in zip(passages, vectors, strict=True))
        generation = db.scalar(select(SourceGeneration).where(SourceGeneration.id == generation_id).with_for_update())
        generation.search_ready_at = generation.search_ready_at or datetime.now(UTC)
        derivation.status, derivation.completed_at = "succeeded", datetime.now(UTC)
    return derivation_id


def expansions(plan) -> list[str]:
    """The reader's own words, then appearance-oriented queries for the subject's visible label and moment."""
    label = plan.subject.label
    found = [plan.query] if plan.query else []
    found += [a.format(label=label) for a in ASPECTS.get(plan.subject.kind, ASPECTS["object"])]
    if terms(plan):
        found.append(" ".join([label, *terms(plan)]))
    return found


def semantic(db, plan, embedder: Embedder, limit: int = LIMIT) -> list[Candidate] | None:
    """Nearest passages by cosine distance to any expansion; None when this embedder has no index here."""
    derivation = db.scalar(select(Derivation).where(
        Derivation.generation_id == plan.generation_id, Derivation.stage == STAGE,
        Derivation.processing_version == index_version(embedder), Derivation.status == "succeeded"))
    if derivation is None:
        return None
    distances = [PassageEmbedding.embedding.cosine_distance(v) for v in embedder.queries(expansions(plan))]
    nearest = func.least(*distances) if len(distances) > 1 else distances[0]
    rows = db.execute(in_scope(select(Passage.id, func.length(Passage.text)), plan)
                      .join(PassageEmbedding, PassageEmbedding.passage_id == Passage.id)
                      .where(PassageEmbedding.derivation_id == derivation.id)
                      .order_by(nearest, Passage.ordinal).limit(limit)).all()
    return [Candidate(pid, 0, length, {"semantic": i}) for i, (pid, length) in enumerate(rows, 1)]
