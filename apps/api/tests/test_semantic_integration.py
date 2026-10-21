import os

import pytest
from app.models.embeddings import PassageEmbedding
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.providers.embeddings import HashedEmbeddings, LocalEmbeddings
from app.services.narrative.eligibility import visible_narrative
from app.services.retrieval.semantic import expansions, index_passages, semantic
from sqlalchemy import func, select

pytestmark = pytest.mark.integration


def texts(story, plan, candidates):
    view = visible_narrative(story.db, story.db.get(SourceGeneration, plan.generation_id), plan.cutoff)
    return [view.passages[c.passage_id][1] for c in candidates]


def rows(story, derivation_id):
    return story.db.scalar(select(func.count()).select_from(PassageEmbedding)
                           .where(PassageEmbedding.derivation_id == derivation_id))


def other_generation(story):
    return story.db.scalar(select(SourceGeneration.id).where(SourceGeneration.document_id == story.other_document))


def test_similarity_candidates_stay_inside_the_work_and_reading_boundary(story):
    embedder = HashedEmbeddings()
    first = index_passages(story.engine, story.generation, embedder)
    assert index_passages(story.engine, story.generation, embedder) == first
    index_passages(story.engine, other_generation(story), embedder)
    story.db.expire_all()
    assert rows(story, first) == 14
    assert story.db.get(SourceGeneration, story.generation).search_ready_at is not None

    plan = story.plan(2, query="Arthur in battle")
    assert expansions(plan) == ["the appearance of Arthur: face, hair, eyes, skin and build",
                                "what Arthur wore: clothes, armour, accessories and things carried",
                                "Arthur in battle"]
    found = semantic(story.db, plan, embedder)
    chapters = {story.db.get(Passage, c.passage_id).chapter_ordinal for c in found}
    other = set(story.db.scalars(select(Passage.id).where(Passage.document_id == story.other_document)))
    assert found and chapters <= {1, 2} and not {c.passage_id for c in found} & other
    assert [c.paths for c in found] == [{"semantic": i} for i in range(1, len(found) + 1)]
    assert all(c.start == 0 and c.end == len(t) for c, t in zip(found, texts(story, plan, found)))


def test_embedding_models_never_mix_and_a_model_change_rebuilds(story):
    old, new = HashedEmbeddings("hashed-v1"), HashedEmbeddings("hashed-v2")
    old_id = index_passages(story.engine, story.generation, old)
    plan = story.plan(None, query="brass compass")
    assert semantic(story.db, plan, new) is None
    new_id = index_passages(story.engine, story.generation, new)
    story.db.expire_all()
    assert new_id != old_id and rows(story, old_id) == rows(story, new_id) == 14
    versions = dict(story.db.execute(select(Derivation.id, Derivation.processing_version)
                                     .where(Derivation.stage == "index")).all())
    assert versions[old_id] == "index-v1/deterministic/hashed-v1/d768"
    assert "compass" in texts(story, plan, semantic(story.db, plan, new))[0]

    class Small(HashedEmbeddings):
        dimension = 256
    with pytest.raises(ValueError):
        index_passages(story.engine, story.generation, Small("small"))


@pytest.mark.skipif(os.environ.get("VISION_LOCAL_MODELS") != "1",
                    reason="Set VISION_LOCAL_MODELS=1 to run the pinned EmbeddingGemma weights (about 1.2 GB, CPU)")
def test_local_embeddings_retrieve_unnamed_descriptions(story):
    embedder = LocalEmbeddings()
    index_passages(story.engine, story.generation, embedder)
    # The dinner passage never names the house; only similarity can connect it to the place.
    for query, cutoff, expected in [
        ("the house by the ash tree at dinner", 3, "Warm candlelight lit the room."),
        ("the house by the ash tree in spring", None, "builders had restored the slate roof"),
    ]:
        plan = story.plan(cutoff, query=query)
        ranked = texts(story, plan, semantic(story.db, plan, embedder))
        assert any(expected in t for t in ranked[:5])
