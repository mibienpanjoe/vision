import secrets
from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import COOKIE_NAME, token_hash
from app.main import create_app
from app.models.access import LoginSession, Principal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture
def recovery_clients(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    tokens = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
    with Session(database) as db:
        for index, token in enumerate(tokens):
            owner = Principal(username=f"recovery_{index}", password_hash="unused synthetic account")
            db.add(owner)
            db.flush()
            db.add(LoginSession(owner_id=owner.id, token_hash=token_hash(token), expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as first, TestClient(create_app(), base_url="http://127.0.0.1") as other:
        for client, token in zip((first, other), tokens, strict=True):
            client.cookies.set(COOKIE_NAME, token)
        accepted = first.post("/v1/works", data={"title": "Recovery source", "format": "txt"},
                              files={"file": ("source.txt", b"One paragraph.\n\nAnother paragraph.")},
                              headers={**ORIGIN, "Idempotency-Key": "recovery-source"}).json()
        endpoint = f"/v1/works/{accepted['work']['id']}/ingestions/{accepted['job']['id']}"
        yield first, other, endpoint, accepted


def mutation(client, endpoint, action, revision, key):
    return client.post(endpoint + "/" + action, headers={**ORIGIN, "If-Match": f'"{revision}"', "Idempotency-Key": key})


def test_cancel_retry_replay_stale_revision_and_owner_guards(recovery_clients):
    client, other, endpoint, accepted = recovery_clients
    first = client.get(endpoint)
    revision = first.json()["revision"]
    assert first.headers["etag"] == f'"{revision}"'
    assert mutation(other, endpoint, "cancel", revision, "other").status_code == 404
    assert client.post(endpoint + "/cancel", headers={**ORIGIN, "Idempotency-Key": "missing-revision"}).status_code == 428
    cancelled = mutation(client, endpoint, "cancel", revision, "cancel-one")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert mutation(client, endpoint, "cancel", revision, "cancel-one").json() == cancelled.json()
    assert mutation(client, endpoint, "retry", revision, "stale").status_code == 412
    retried = mutation(client, endpoint, "retry", cancelled.json()["revision"], "retry-one")
    assert retried.status_code == 200 and retried.json()["status"] == "queued"
    assert mutation(client, endpoint, "cancel", revision, "retry-one").status_code == 409


def test_running_cancel_is_confirmed_only_after_worker_observes_it(recovery_clients, database, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app.models.passages import Passage
    from app.services.ingestion import parse
    from sqlalchemy import func, select

    client, _, endpoint, accepted = recovery_clients
    entered, release = threading.Event(), threading.Event()
    actual_parse = parse.parse_text
    def gated_parse(data, source_format):
        entered.set()
        assert release.wait(timeout=10)
        return actual_parse(data, source_format)
    monkeypatch.setattr(parse, "parse_text", gated_parse)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(parse.execute_ingestion, accepted["job"]["id"])
        try:
            assert entered.wait(timeout=5)
            running = client.get(endpoint).json()
            assert running["status"] == "running"
            pending = mutation(client, endpoint, "cancel", running["revision"], "cancel-running")
            assert pending.json()["status"] == "running" and pending.json()["cancel_requested"]
        finally:
            release.set()
        future.result(timeout=10)
    assert client.get(endpoint).json()["status"] == "cancelled"
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Passage)) == 0


def test_real_worker_kill_recovery_and_restart_preserve_one_output_set(recovery_clients, database, monkeypatch, tmp_path):
    import os
    import signal
    import subprocess
    import time
    import uuid
    from pathlib import Path

    from app.models.passages import Passage
    from app.models.works import IngestionAttempt
    from app.services.dispatch import dispatch_ingestions
    from app.services.ingestion.jobs import recover_ingestions
    from sqlalchemy import func, select

    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Set VISION_TEST_REDIS_URL for worker crash recovery")
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    client, _, _, _ = recovery_clients
    count = 19000
    accepted = client.post("/v1/works", data={"title": "Crash recovery source", "format": "txt"},
                           files={"file": ("large.txt", ("a" * 70 + "\n\n").encode() * count)},
                           headers={**ORIGIN, "Idempotency-Key": "crash-source"}).json()
    job_id = uuid.UUID(accepted["job"]["id"])
    document_id = uuid.UUID(accepted["work"]["document_id"])
    endpoint = f"/v1/works/{accepted['work']['id']}/ingestions/{job_id}"
    api = Path(__file__).parents[1]
    worker = None
    with (tmp_path / "recovery-worker.log").open("w") as log:
        def start_worker():
            return subprocess.Popen([str(api / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1", "--threads", "1"],
                                    cwd=api, env=os.environ.copy(), stdout=log, stderr=log, start_new_session=True)
        try:
            worker = start_worker()
            for _ in range(1000):
                status = client.get(endpoint).json()["status"]
                if status == "running":
                    break
                assert status == "queued", status
                time.sleep(0.01)
            else:
                pytest.fail("Worker never entered its persisted running stage")
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=10)
            worker = None
            for _ in range(30):
                if recover_ingestions(database):
                    break
                time.sleep(0.1)
            else:
                pytest.fail("Interrupted worker lease was not released")
            with Session(database) as db:
                assert db.scalar(select(func.count()).select_from(Passage).where(Passage.document_id == document_id)) == 0
            assert dispatch_ingestions(database, job_id) == 1
            worker = start_worker()
            for _ in range(300):
                result = client.get(endpoint).json()
                if result["status"] in {"failed", "succeeded"}:
                    break
                time.sleep(0.1)
            assert result["status"] == "succeeded" and result["attempts"] == 2, result
        finally:
            if worker is not None:
                worker.terminate()
                worker.wait(timeout=15)
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Passage).where(Passage.document_id == document_id)) == count
        attempts = list(db.scalars(select(IngestionAttempt).where(IngestionAttempt.job_id == job_id).order_by(IngestionAttempt.number)))
        assert [attempt.outcome for attempt in attempts] == ["abandoned", "succeeded"]


def test_failed_parse_retry_budget_is_bounded(recovery_clients, database):
    import uuid

    from app.models.works import IngestionJob
    from app.services.ingestion.parse import execute_ingestion

    client, _, endpoint, accepted = recovery_clients
    job_id = uuid.UUID(accepted["job"]["id"])
    with Session(database) as db:
        job = db.get(IngestionJob, job_id)
        job.processing_version = "unsupported-test-version"
        db.commit()
    for attempt in range(1, 4):
        execute_ingestion(str(job_id))
        job = client.get(endpoint).json()
        assert job["status"] == "failed" and job["attempts"] == attempt
        response = mutation(client, endpoint, "retry", job["revision"], f"retry-{attempt}")
        assert response.status_code == (200 if attempt < 3 else 429)
