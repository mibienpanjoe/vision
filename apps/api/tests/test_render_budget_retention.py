"""A book purge or an older snapshot must not refund the owner's image budget."""


import pytest
from app.main import create_app
from app.models.passages import Chapter
from app.models.works import Document
from app.operations import backup, export_deletions, restore
from app.providers.embeddings import HashedEmbeddings
from app.services.narrative.appearance import derive_appearance
from app.services.narrative.entities import derive_entities
from app.services.retrieval.semantic import index_passages
from app.services.works.deletion import execute_purge
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.test_deletion_lifecycle import delete
from tests.test_entity_extraction import fixture_adapter
from tests.test_recovery_drill import new_roots, target  # noqa: F401
from tests.test_refinement import ORIGIN
from tests.test_render_contract import enable
from tests.test_security_boundaries import world  # noqa: F401

pytestmark = pytest.mark.integration


def other_spec(state):
    clients, story, _, other, *_ = state
    document = story.db.get(Document, story.other_document)
    generation = document.current_generation_id
    chapter = story.db.scalar(select(Chapter.id).where(Chapter.document_id == document.id, Chapter.ordinal == 3))
    story.db.rollback()
    entities = derive_entities(story.engine, generation, fixture_adapter())
    derive_appearance(story.engine, generation, entities)
    index_passages(story.engine, generation, HashedEmbeddings())
    response = clients["reader"].post(f"/v1/works/{other}/visualizations", json={
        "query": "Arthur at home after the war", "through_chapter_id": str(chapter)},
        headers={**ORIGIN, "Idempotency-Key": "other-book-profile"})
    assert response.status_code == 201, response.text
    return other, response.json()["visualization"]["id"]


def reserve(client, work_id, visualization_id, key):
    return client.post(f"/v1/works/{work_id}/visualizations/{visualization_id}/renders",
        json={"specification_revision": 1}, headers={**ORIGIN, "Idempotency-Key": key})


def test_purging_a_book_cannot_refund_a_used_image_reservation(world, monkeypatch):  # noqa: F811
    clients, _, ids, *_ = world  # one completed render already consumed this owner's only slot
    other, view = other_spec(world)
    enable(monkeypatch, 1)
    assert reserve(clients["reader"], other, view, "before-purge").status_code == 429
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
    execute_purge(ids["work_id"])
    denied = reserve(clients["reader"], other, view, "after-purge")
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "RENDER_LIMIT"


def test_restore_keeps_image_reservations_consumed_after_the_snapshot(world, target, tmp_path, monkeypatch):  # noqa: F811
    clients, story, ids, *_ = world
    story.db.close()
    archive, ledger = tmp_path / "snapshot", tmp_path / "latest.json"
    backup(story.engine, archive)
    assert reserve(clients["reader"], ids["work_id"], ids["visualization_id"], "after-snapshot").status_code == 202
    export_deletions(story.engine, ledger)
    new_roots(monkeypatch, tmp_path)
    restore(target, archive, ledger)
    monkeypatch.setenv("DATABASE_URL", target.url.render_as_string(hide_password=False))
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "reader",
            "password": "synthetic query plan passphrase"}, headers=ORIGIN).status_code == 200
        denied = reserve(client, ids["work_id"], ids["visualization_id"], "after-restore")
        assert denied.status_code == 429
        assert denied.json()["error"]["code"] == "RENDER_LIMIT"


def test_budget_migration_round_trip_backfills_receipts_and_fails_closed_for_erased_history(world):  # noqa: F811
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from app.models.access import Principal
    from sqlalchemy.orm import Session

    clients, story, ids, other, *_ = world
    with Session(story.engine) as db:
        owners = {p.username: p.id for p in db.scalars(select(Principal))}
    story.db.close()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0025")
    command.upgrade(config, "head")
    with Session(story.engine) as db:
        assert db.get(Principal, owners["reader"]).render_reservations_used == 1
        assert db.get(Principal, owners["stranger"]).render_reservations_used == 0
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
    execute_purge(ids["work_id"])
    # An older candidate did not retain usage after purge. A round trip must not invent a fresh budget.
    command.downgrade(config, "0025")
    command.upgrade(config, "head")
    with Session(story.engine) as db:
        assert db.get(Principal, owners["reader"]).render_reservations_used == 5
        assert db.get(Principal, owners["stranger"]).render_reservations_used == 0
    assert clients["reader"].get(f"/v1/works/{other}").status_code == 200
