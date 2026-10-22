import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.models.model_runs import Derivation
from app.models.visualizations import VisualizationRevision
from sqlalchemy import select
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


def stored(api):
    _, clients, work_id, story = api
    response = clients["reader"].post(f"/v1/works/{work_id}/visualizations", json={
        "query": "Arthur at home after the war", "through_chapter_id": str(story.chapters[3])},
        headers={**ORIGIN, "Idempotency-Key": "refinement-source"})
    assert response.status_code == 201, response.text
    return response.json()["visualization"]


def test_revision_request_and_dependency_inputs_are_preserved_through_migration(api):
    original = stored(api)
    _, clients, work_id, story = api
    view = original["result"]["data"]
    inputs = view["lineage"]["inputs"]
    assert set(inputs) == {"entities", "appearance", "index"}
    consolidation = story.db.get(Derivation, uuid.UUID(view["lineage"]["consolidation_id"]))
    assert inputs["entities"] == str(consolidation.input_derivation_id)
    assert "steel armor" in view["generation"]["excluded_values"]
    story.db.rollback()
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database == story.engine.url.database and target.database.startswith("vision_test_")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0019")
    command.upgrade(config, "head")
    revision = story.db.scalar(select(VisualizationRevision).where(VisualizationRevision.visualization_id == uuid.UUID(original["id"])))
    assert revision.request == original["request"]
    response = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}/revisions/1")
    assert response.status_code == 200 and response.json() == original


def refine(api, original, *, key="refine-one", revision=1, client="reader", **body):
    _, clients, work_id, _ = api
    return clients[client].post(f"/v1/works/{work_id}/visualizations/{original['id']}/refinements",
                               json={"style": "charcoal", "creative_mode": "interpretation", **body},
                               headers={**ORIGIN, "Idempotency-Key": key, **({"If-Match": f'"{revision}"'} if revision is not None else {})})


def test_refinement_is_conditional_idempotent_and_keeps_immutable_evidence(api):
    original = stored(api)
    _, clients, work_id, story = api
    assert refine(api, original, revision=None).status_code == 428
    assert refine(api, original, client="stranger").status_code == 404
    spec = original["result"]["data"]
    attire = next(trait for trait in spec["subject"]["traits"] if trait["attribute"] == "attire")
    locks = [{"entity_id": spec["subject"]["entity"]["entity_ids"][0], "attribute": "attire", "value": attire["values"][0]}]
    response = refine(api, original, locks=locks)
    assert response.status_code == 200, response.text
    newer = response.json()
    assert response.headers["etag"] == '"2"' and newer["revision"] == 2
    assert newer["result"]["data"]["subject"] == spec["subject"]
    assert newer["result"]["data"]["locks"] == locks
    assert newer["request"]["style"] == "charcoal" and newer["request"]["creative_mode"] == "interpretation"
    assert refine(api, original, locks=locks).json() == newer
    assert refine(api, original, locks=locks, style="ink").status_code == 409
    assert refine(api, original, key="stale").status_code == 412
    weak = clients["reader"].post(f"/v1/works/{work_id}/visualizations/{original['id']}/refinements",
        json={"style": "ink", "creative_mode": "canon_first"},
        headers={**ORIGIN, "Idempotency-Key": "weak", "If-Match": 'W/"2"'})
    assert weak.status_code == 412
    old = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}/revisions/1").json()
    assert old == original
    replay = clients["reader"].post(f"/v1/works/{work_id}/visualizations", json=original["request"],
                                     headers={**ORIGIN, "Idempotency-Key": "refinement-source"})
    assert replay.json()["visualization"] == original
    assert len(story.db.scalars(select(VisualizationRevision).where(VisualizationRevision.visualization_id == uuid.UUID(original["id"]))).all()) == 2


def test_unsupported_lock_prompt_conflict_and_scope_fields_cannot_rewrite_canon(api):
    original = stored(api)
    entity = original["result"]["data"]["subject"]["entity"]["entity_ids"][0]
    denied = refine(api, original, locks=[{"entity_id": entity, "attribute": "attire", "value": "golden armor"}])
    assert (denied.status_code, denied.json()["error"]["code"]) == (409, "LOCK_UNSUPPORTED")
    denied = refine(api, original, style="steel armor")
    assert (denied.status_code, denied.json()["error"]["code"]) == (409, "PROMPT_GATE_FAILED")
    assert refine(api, original, moment={"kind": "age", "years": 10}).status_code == 422
    _, clients, work_id, _ = api
    path = f"/v1/works/{work_id}/visualizations/{original['id']}"
    assert clients["reader"].get(path).json() == original
    too_large = clients["reader"].post(path + "/refinements", content=b" " * 32769,
        headers={**ORIGIN, "Content-Type": "application/json", "Idempotency-Key": "oversize", "If-Match": '"1"'})
    assert too_large.status_code == 413


def test_changed_entity_dependencies_require_a_new_reconstruction(api):
    from app.services.narrative.entities import derive_entities
    from tests.test_entity_extraction import fixture_adapter

    original = stored(api)
    story = api[3]
    derive_entities(story.engine, story.generation, fixture_adapter("changed-v2"))
    response = refine(api, original)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "DEPENDENCIES_CHANGED")


@pytest.mark.parametrize("stage", ["appearance", "index"])
def test_changed_appearance_or_embedding_configuration_refuses_refinement(api, monkeypatch, stage):
    from datetime import UTC, datetime

    from app.providers.embeddings import HashedEmbeddings
    from app.services.narrative import pipeline

    original = stored(api)
    story = api[3]
    if stage == "index":
        monkeypatch.setattr(pipeline, "local_embedder", lambda: HashedEmbeddings("changed-index"))
    else:
        story.db.add(Derivation(generation_id=story.generation, stage="appearance", processing_version="changed-appearance",
            input_derivation_id=uuid.UUID(original["result"]["data"]["lineage"]["inputs"]["entities"]),
            status="succeeded", completed_at=datetime.now(UTC)))
        story.db.commit()
    response = refine(api, original)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "DEPENDENCIES_CHANGED")


def test_source_generation_change_refuses_refinement_but_retains_old_citations(api):
    from app.models.generations import SourceGeneration
    from app.models.works import Document

    original = stored(api)
    _, clients, work_id, story = api
    old = story.db.get(SourceGeneration, story.generation)
    newer = SourceGeneration(document_id=old.document_id, ordinal=2, parser_revision="synthetic-v2", idempotency_key="new-source")
    story.db.add(newer)
    story.db.flush()
    story.db.get(Document, old.document_id).current_generation_id = newer.id
    story.db.commit()
    response = refine(api, original)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "SCOPE_CHANGED")
    spec = original["result"]["data"]
    quote = spec["subject"]["traits"][0]["evidence"][0]
    evidence = clients["reader"].post(f"/v1/works/{work_id}/evidence", json={"span": quote,
        "parser_revision": spec["scope"]["parser_revision"],
        "reading_boundary": {"mode": "through_chapter", "chapter_id": spec["scope"]["through_chapter_id"]}}, headers=ORIGIN)
    assert evidence.status_code == 200


def test_concurrent_refinements_cannot_both_overwrite_the_same_revision(api):
    from concurrent.futures import ThreadPoolExecutor

    from app.main import create_app
    from fastapi.testclient import TestClient

    original = stored(api)
    work_id = api[2]

    def submit(key):
        with TestClient(create_app(), base_url="http://127.0.0.1") as client:
            client.post("/v1/auth/login", json={"username": "reader", "password": "synthetic query plan passphrase"}, headers=ORIGIN)
            return client.post(f"/v1/works/{work_id}/visualizations/{original['id']}/refinements",
                json={"style": key, "creative_mode": "interpretation"},
                headers={**ORIGIN, "If-Match": '"1"', "Idempotency-Key": key}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, ["charcoal", "ink"])) == [200, 412]


def test_revision_requests_survive_a_full_refinement_schema_round_trip(api):
    original = stored(api)
    edited = refine(api, original).json()
    _, clients, work_id, story = api
    story.db.rollback()
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database == story.engine.url.database and target.database.startswith("vision_test_")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0019")
    command.upgrade(config, "head")
    for number, expected in [(1, original), (2, edited)]:
        response = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}/revisions/{number}")
        assert response.status_code == 200 and response.json() == expected
