"""Real render reservations and execution in PostgreSQL with synthetic image adapters; no live provider."""

import hashlib
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.core.storage import SourceLease
from app.models.renders import RenderJob
from app.providers.images import AcceptanceUnknown, Image, RenderPolicy, RenderRejected
from app.services.ingestion.jobs import job_lock
from app.services.visualization import render
from tests.image_fixtures import PNG, SyntheticImages
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


class Recording(SyntheticImages):
    def __init__(self, outcome=None):
        self.prompts, self.outcome = [], outcome

    def generate(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome() if self.outcome else Image(PNG, "image/png", {"total_tokens": 3})


def execute(monkeypatch, adapter, job, times=1):
    monkeypatch.setattr(render, "image_adapter", lambda: adapter)
    for _ in range(times):
        render.execute_render(job["id"])


def current(api, job):
    _, clients, work_id, _ = api
    return clients["reader"].get(f"/v1/works/{work_id}/renders/{job['id']}").json()


@pytest.fixture
def renders(monkeypatch, tmp_path):
    monkeypatch.setenv("VISION_RENDER_ROOT", str(tmp_path / "renders"))
    return tmp_path / "renders"


def test_worker_sends_only_the_specification_prompt_once_and_keeps_private_output(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch)
    job = submit(api, original).json()
    adapter = Recording()
    execute(monkeypatch, adapter, job, times=2)
    generation = original["result"]["data"]["generation"]
    assert adapter.prompts == [generation["prompt"]]
    assert generation["negative_prompt"] and generation["negative_prompt"] not in adapter.prompts[0]
    view = current(api, job)
    assert (view["status"], view["revision"], view["error_code"]) == ("succeeded", 3, None)
    assert (view["output_sha256"], view["output_media_type"]) == (hashlib.sha256(PNG).hexdigest(), "image/png")
    assert view["completed_at"] and submit(api, original).json() == view
    *_, story = api
    row = story.db.get(RenderJob, uuid.UUID(job["id"]))
    story.db.refresh(row)
    output = renders / row.output_reference
    assert output.read_bytes() == PNG and output.stat().st_mode & 0o077 == 0
    assert row.settings == {**SyntheticImages.settings,
                            "prompt_sha256": hashlib.sha256(generation["prompt"].encode()).hexdigest()}
    assert row.usage == {"total_tokens": 3} and row.output_reference not in str(view)


def failing_write(lease, data):
    lease.stream.write(data[:4])
    lease.stream.flush()
    raise OSError("disk full")


@pytest.mark.parametrize(("outcome", "status", "code"), [
    (AcceptanceUnknown(), "acceptance_unknown", "PROVIDER_ACCEPTANCE_UNKNOWN"),
    (RenderRejected("PROVIDER_REJECTED"), "failed", "PROVIDER_REJECTED"),
    (None, "failed", "RENDER_STORAGE_FAILED"),
])
def test_uncertain_rejected_and_unstored_calls_are_honest_and_never_repeated(api, monkeypatch, renders,
                                                                             outcome, status, code):
    original = stored(api)
    enable(monkeypatch)
    job = submit(api, original).json()
    if outcome is None:
        monkeypatch.setattr(SourceLease, "write", failing_write)
    adapter = Recording(outcome)
    execute(monkeypatch, adapter, job, times=2)
    view = current(api, job)
    assert (view["status"], view["error_code"], view["output_sha256"]) == (status, code, None)
    assert len(adapter.prompts) == 1 and not list(renders.glob("*"))
    # The used reservation still counts: a retry is a new, explicit, capped request.
    assert submit(api, original, key="retry").status_code == 429


def test_cancelled_or_unconfigured_jobs_never_call_the_provider(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch, 3)
    _, clients, work_id, _ = api
    cancelled = submit(api, original).json()
    clients["reader"].post(f"/v1/works/{work_id}/renders/{cancelled['id']}/cancel", json={},
                           headers={**ORIGIN, "Idempotency-Key": "cancel", "If-Match": '"1"'})
    adapter = Recording()
    execute(monkeypatch, adapter, cancelled)
    assert current(api, cancelled)["status"] == "cancelled"
    unconfigured = submit(api, original, key="second").json()
    execute(monkeypatch, None, unconfigured)
    # A reservation made for one model is never executed by another.
    changed = submit(api, original, key="third").json()
    adapter.model = "another-model"
    execute(monkeypatch, adapter, changed)
    assert adapter.prompts == []
    for job in (unconfigured, changed):
        assert (current(api, job)["status"], current(api, job)["error_code"]) == ("failed", "RENDER_NOT_CONFIGURED")


def test_cancel_during_a_running_call_keeps_its_outcome(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch)
    _, clients, work_id, _ = api
    job = submit(api, original).json()
    path = f"/v1/works/{work_id}/renders/{job['id']}/cancel"

    def late_cancel():
        response = clients["reader"].post(path, json={}, headers={**ORIGIN, "Idempotency-Key": "late", "If-Match": '"2"'})
        assert response.json()["status"] == "running" and response.json()["cancel_requested"] is True
        return Image(PNG, "image/png")
    execute(monkeypatch, Recording(late_cancel), job)
    view = current(api, job)
    assert (view["status"], view["cancel_requested"], view["revision"]) == ("succeeded", True, 4)
    assert view["output_sha256"] == hashlib.sha256(PNG).hexdigest()


def test_interrupted_claims_settle_as_acceptance_unknown_without_another_call(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch, 3)
    *_, story = api
    jobs = [submit(api, original, key=f"claim-{n}").json() for n in range(3)]
    for job in jobs:
        story.db.get(RenderJob, uuid.UUID(job["id"])).status = "running"
    story.db.commit()
    adapter = Recording()
    execute(monkeypatch, adapter, jobs[0])
    with job_lock(story.engine, uuid.UUID(jobs[2]["id"])) as held:
        assert held and render.recover_renders(story.engine) == 1
    assert adapter.prompts == []
    assert [current(api, job)["status"] for job in jobs] == ["acceptance_unknown", "acceptance_unknown", "running"]
    assert current(api, jobs[0])["error_code"] == "RENDER_INTERRUPTED"


def test_real_worker_renders_after_a_failed_enqueue_is_dispatched(api, monkeypatch, renders):
    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Set VISION_TEST_REDIS_URL to opt into a real Redis worker test")
    original = stored(api)
    enable(monkeypatch)
    *_, story = api
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    job = submit(api, original).json()
    assert job["dispatched"] is False and job["status"] == "queued"
    monkeypatch.setenv("REDIS_URL", redis_url)
    api_root = Path(__file__).parents[1]
    worker = subprocess.Popen([str(api_root / ".venv/bin/dramatiq"), "tests.render_worker", "--processes", "1",
                               "--threads", "1", "--queues", "render"], cwd=api_root, env=os.environ.copy(),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        from app.services.dispatch import dispatch_renders
        assert dispatch_renders(story.engine) == 1
        for _ in range(300):
            view = current(api, job)
            if view["status"] != "queued" and view["status"] != "running":
                break
            time.sleep(0.1)
        assert (view["status"], view["dispatched"], view["output_media_type"]) == ("succeeded", True, "image/png")
        assert dispatch_renders(story.engine) == 0
    finally:
        worker.terminate()
        worker.wait(timeout=15)
