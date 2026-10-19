import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.services.dispatch import dispatch_pending
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
PASSWORD = "synthetic queue test passphrase"


def test_real_queue_pending_replay_ownership_restart_and_dispatch_recovery(
    database, monkeypatch, tmp_path
):
    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Set VISION_TEST_REDIS_URL to opt into a real Redis worker test")
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    with Session(database) as db:
        db.add_all(
            [
                Principal(username=name, password_hash=hash_password(PASSWORD))
                for name in ("queue_alice", "queue_bruno")
            ]
        )
        db.commit()
    api = Path(__file__).parents[1]
    worker = None
    log = (tmp_path / "worker.log").open("w")

    def start_worker():
        return subprocess.Popen(
            [
                str(api / ".venv/bin/dramatiq"),
                "app.workers.bootstrap",
                "--processes",
                "1",
                "--threads",
                "1",
            ],
            cwd=api,
            env=os.environ.copy(),
            stdout=log,
            stderr=log,
        )

    def stop_worker(process):
        process.terminate()
        process.wait(timeout=15)

    def wait_result(client, job_id, expected):
        for _ in range(150):
            result = client.get(f"/v1/jobs/{job_id}").json()
            if result["status"] == "succeeded":
                assert result["result"] == expected
                assert result["attempts"] == 1
                return
            time.sleep(0.1)
        pytest.fail("Real worker did not persist the expected result")

    try:
        app = create_app()
        with TestClient(app, base_url="http://127.0.0.1") as client:
            assert (
                client.post(
                    "/v1/auth/login",
                    json={"username": "queue_alice", "password": PASSWORD},
                    headers=ORIGIN,
                ).status_code
                == 200
            )
            headers = {**ORIGIN, "Idempotency-Key": "probe-one"}
            response = client.post("/v1/jobs", json={"value": 7}, headers=headers)
            assert response.status_code == 202
            job_id = response.json()["id"]
            assert response.json()["status"] == "queued"
            assert not response.json()["dispatch_pending"]
            assert (
                client.post("/v1/jobs", json={"value": 7}, headers=headers).json()["id"]
                == job_id
            )
            assert (
                client.post("/v1/jobs", json={"value": 9}, headers=headers).status_code
                == 409
            )
            worker = start_worker()
            wait_result(client, job_id, 8)
            stop_worker(worker)
            worker = None
            pending = client.post(
                "/v1/jobs",
                json={"value": 10},
                headers={**ORIGIN, "Idempotency-Key": "probe-two"},
            ).json()
            assert pending["status"] == "queued"
            worker = start_worker()
            wait_result(client, pending["id"], 11)
            stop_worker(worker)
            worker = None
            monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
            unpublished = client.post(
                "/v1/jobs",
                json={"value": 20},
                headers={**ORIGIN, "Idempotency-Key": "probe-three"},
            )
            assert unpublished.status_code == 202
            assert unpublished.json()["dispatch_pending"]
            monkeypatch.setenv("REDIS_URL", redis_url)
            assert dispatch_pending(database) == 1
            worker = start_worker()
            wait_result(client, unpublished.json()["id"], 21)
            stop_worker(worker)
            worker = None
            assert client.post("/v1/auth/logout", headers=ORIGIN).status_code == 204
            assert client.get(f"/v1/jobs/{job_id}").status_code == 401
            assert (
                client.post(
                    "/v1/auth/login",
                    json={"username": "queue_bruno", "password": PASSWORD},
                    headers=ORIGIN,
                ).status_code
                == 200
            )
            assert client.get(f"/v1/jobs/{job_id}").status_code == 404
    finally:
        if worker is not None:
            stop_worker(worker)
        log.close()
