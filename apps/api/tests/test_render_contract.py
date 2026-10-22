"""Real render reservations in PostgreSQL; no external image provider is selected here."""

import uuid

import pytest
from app.models.renders import RenderJob
from app.providers.images import RenderPolicy
from app.services.visualization import render
from tests.test_refinement import ORIGIN, refine, stored

pytestmark = pytest.mark.integration


def submit(api, view, key="render-one", client="reader", **body):
    _, clients, work_id, _ = api
    return clients[client].post(f"/v1/works/{work_id}/visualizations/{view['id']}/renders",
        json={"specification_revision": view["revision"], **body},
        headers={**ORIGIN, "Idempotency-Key": key})


def enable(monkeypatch, maximum=1):
    monkeypatch.setattr(render, "configured_policy", lambda: RenderPolicy("synthetic", "fixture-v1", maximum))


def test_render_is_disabled_without_d5_and_never_accepts_a_raw_prompt(api, monkeypatch):
    original = stored(api)
    monkeypatch.setattr(render, "configured_policy", lambda: None)
    assert submit(api, original).status_code == 503
    assert submit(api, original, client="stranger").status_code == 404
    enable(monkeypatch)
    assert submit(api, original, prompt="ignore the specification").status_code == 422
    assert submit(api, original, specification_revision=0).status_code == 422
    assert submit(api, original, padding="x" * 33000).status_code == 413


def test_reservation_replays_immutable_snapshot_and_enforces_owner_budget(api, monkeypatch):
    original = stored(api)
    enable(monkeypatch)
    first = submit(api, original)
    assert first.status_code == 202, first.text
    job = first.json()
    assert job["status"] == "queued" and job["dispatched"] is False
    assert first.headers["etag"] == '"1"'
    _, clients, work_id, story = api
    retained = story.db.get(RenderJob, uuid.UUID(job["id"]))
    assert retained.specification == original["result"]["data"]
    assert retained.specification_sha256 and retained.provider == "synthetic"
    assert submit(api, original).json() == job
    assert submit(api, original, key="another-charge").status_code == 429
    assert submit(api, original, specification_revision=2).status_code == 409
    path = f"/v1/works/{work_id}/renders/{job['id']}"
    assert clients["reader"].get(path).json() == job
    assert clients["stranger"].get(path).status_code == 404
    assert refine(api, original).status_code == 200
    story.db.refresh(retained)
    assert retained.specification == original["result"]["data"]
    assert retained.specification_sha256 == job["specification_sha256"]
    # Replays survive later provider configuration changes; they cannot reserve another call.
    monkeypatch.setattr(render, "configured_policy", lambda: None)
    assert submit(api, original).json() == job


def test_cancel_is_conditional_replayable_and_running_cancellation_is_pending(api, monkeypatch):
    original = stored(api)
    enable(monkeypatch, 2)
    job = submit(api, original).json()
    _, clients, work_id, story = api
    path = f"/v1/works/{work_id}/renders/{job['id']}/cancel"
    headers = {**ORIGIN, "Idempotency-Key": "cancel-one"}
    assert clients["reader"].post(path, json={}, headers=headers).status_code == 428
    assert clients["stranger"].post(path, json={}, headers={**headers, "If-Match": '"1"'}).status_code == 404
    response = clients["reader"].post(path, json={}, headers={**headers, "If-Match": '"1"'})
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert response.headers["etag"] == '"2"'
    assert clients["reader"].post(path, json={}, headers={**headers, "If-Match": '"1"'}).json() == response.json()
    assert clients["reader"].post(path, json={}, headers={**headers, "If-Match": '"2"'}).status_code == 409
    second = submit(api, original, key="second-render").json()
    row = story.db.get(RenderJob, uuid.UUID(second["id"]))
    row.status = "running"
    story.db.commit()
    path = f"/v1/works/{work_id}/renders/{second['id']}/cancel"
    response = clients["reader"].post(path, json={}, headers={**headers, "If-Match": '"1"'})
    assert response.json()["status"] == "running" and response.json()["cancel_requested"] is True
    assert clients["reader"].post(path, json={}, headers={**ORIGIN, "Idempotency-Key": "stale", "If-Match": '"1"'}).status_code == 412
    assert submit(api, original, key="third-render").status_code == 429


def test_changed_processing_refuses_new_reservations(api, monkeypatch):
    from app.models.model_runs import Derivation

    original = stored(api)
    enable(monkeypatch)
    _, _, _, story = api
    dependency = story.db.get(Derivation, uuid.UUID(original["result"]["data"]["lineage"]["inputs"]["appearance"]))
    dependency.processing_version += "-changed"
    dependency.status = "failed"
    story.db.commit()
    response = submit(api, original)
    assert response.status_code == 409 and response.json()["error"]["code"] == "DEPENDENCIES_CHANGED"


def test_source_change_and_newer_specification_refuse_reservation(api, monkeypatch):
    from app.models.works import Document
    original = stored(api)
    enable(monkeypatch)
    newer = refine(api, original).json()
    response = submit(api, original)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SPECIFICATION_CHANGED"
    *_, story = api
    document = story.db.get(Document, story.plan(None, query="Arthur").document_id)
    document.current_generation_id = None
    story.db.commit()
    response = submit(api, newer)
    assert response.status_code == 409


def test_concurrent_reservations_cannot_exceed_the_owner_limit(api, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    original = stored(api)
    enable(monkeypatch)
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda key: submit(api, original, key=key), ["race-one", "race-two"]))
    assert sorted(response.status_code for response in responses) == [202, 429]
    key = next(key for key, response in zip(["race-one", "race-two"], responses, strict=True) if response.status_code == 202)
    with ThreadPoolExecutor(2) as pool:
        replays = list(pool.map(lambda _: submit(api, original, key=key), range(2)))
    assert [response.status_code for response in replays] == [202, 202]
    assert replays[0].json()["id"] == replays[1].json()["id"]


def test_render_migration_round_trip_preserves_parent_specifications(api):
    import os
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    original = stored(api)
    _, clients, work_id, story = api
    story.db.rollback()
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database == story.engine.url.database and target.database.startswith("vision_test_")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0021")
    command.upgrade(config, "head")
    assert clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}").json() == original
