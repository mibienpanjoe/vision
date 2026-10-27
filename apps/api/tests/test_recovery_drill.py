"""Restore real PostgreSQL/source/image state into an empty isolated target."""

import uuid

import pytest
from app.main import create_app
from app.models.works import Work, WorkDeletion
from app.operations import SnapshotError, backup, export_deletions, restore
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from tests.test_deletion_lifecycle import delete
from tests.test_security_boundaries import world  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def target(database):
    name = "vision_test_restore_" + uuid.uuid4().hex
    admin = create_engine(database.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(database.url.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as db:
            db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname=:name AND pid<>pg_backend_pid()"), {"name": name})
            db.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def new_roots(monkeypatch, tmp_path):
    for kind in ("SOURCE", "RENDER"):
        monkeypatch.setenv(f"VISION_{kind}_ROOT", str(tmp_path / (kind.lower() + "-restored")))


def test_restore_preserves_exact_sources_specs_images_and_owner_boundaries(world, target, tmp_path, monkeypatch):  # noqa: F811
    clients, story, ids, _, bodies, _ = world
    reader = clients["reader"]
    work = ids["work_id"]
    paths = [f"/v1/works/{work}/original", f"/v1/works/{work}/visualizations/{ids['visualization_id']}/revisions/1",
             f"/v1/works/{work}/renders/{ids['job_id']}/image"]
    expected = [reader.get(path).content for path in paths]
    assert all(reader.get(path).status_code == 200 for path in paths)
    evidence_path = f"/v1/works/{work}/evidence"
    evidence_body = bodies["/v1/works/{work_id}/evidence"]
    origin = {"Origin": "http://127.0.0.1:3000"}
    evidence = reader.post(evidence_path, json=evidence_body, headers=origin)
    assert evidence.status_code == 200
    story.db.close()
    archive = tmp_path / "snapshot"
    manifest = backup(story.engine, archive)
    ledger = tmp_path / "deletions.json"
    export_deletions(story.engine, ledger)
    new_roots(monkeypatch, tmp_path)
    restore(target, archive, ledger)
    monkeypatch.setenv("DATABASE_URL", target.url.render_as_string(hide_password=False))
    with TestClient(create_app(), base_url="http://127.0.0.1") as restored:
        restored.cookies.update(reader.cookies)
        assert restored.get(paths[0]).status_code == 401  # old sessions are revoked
        for owner in ("reader", "stranger"):
            assert restored.post("/v1/auth/login", json={"username": owner,
                "password": "synthetic query plan passphrase"},
                headers={"Origin": "http://127.0.0.1:3000"}).status_code == 200
            for path, content in zip(paths, expected, strict=True):
                response = restored.get(path)
                assert response.status_code == (200 if owner == "reader" else 404)
                if owner == "reader":
                    assert response.content == content
            excerpt = restored.post(evidence_path, json=evidence_body, headers=origin)
            assert excerpt.status_code == (200 if owner == "reader" else 404)
            if owner == "reader":
                assert excerpt.json() == evidence.json()
    assert manifest["objects"] and archive.stat().st_mode & 0o077 == 0
    assert all(p.stat().st_mode & 0o077 == 0 for p in archive.rglob("*") if p.is_file())


def test_latest_deletion_ledger_prevents_resurrection_from_an_older_backup(world, target, tmp_path, monkeypatch):  # noqa: F811
    from app.services.works.deletion import execute_purge

    clients, story, ids, other, *_ = world
    story.db.close()
    archive = tmp_path / "snapshot"
    backup(story.engine, archive)
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
    execute_purge(ids["work_id"])
    ledger = tmp_path / "latest-deletions.json"
    export_deletions(story.engine, ledger)
    new_roots(monkeypatch, tmp_path)
    restore(target, archive, ledger)
    with Session(target) as db:
        assert db.get(Work, uuid.UUID(ids["work_id"])) is None
        assert db.get(Work, uuid.UUID(other)) is not None
        assert db.get(WorkDeletion, uuid.UUID(ids["work_id"])).status == "completed"


def test_restore_refuses_occupied_targets_corruption_and_old_deletion_ledgers(world, target, tmp_path, monkeypatch):  # noqa: F811
    _, story, *_ = world
    story.db.close()
    old_ledger = tmp_path / "old.json"
    export_deletions(story.engine, old_ledger)
    archive = tmp_path / "snapshot"
    backup(story.engine, archive)
    ledger = tmp_path / "latest.json"
    export_deletions(story.engine, ledger)
    with pytest.raises(SnapshotError, match="empty"):
        restore(story.engine, archive, ledger)
    new_roots(monkeypatch, tmp_path)
    with pytest.raises(SnapshotError, match="older"):
        restore(target, archive, old_ledger)
    with (archive / "database.dump").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(SnapshotError, match="integrity"):
        restore(target, archive, ledger)
    assert inspect(target).get_table_names() == []


def test_backup_refuses_a_held_worker_lease(world, tmp_path):  # noqa: F811
    from app.services.ingestion.jobs import job_lock

    _, story, *_ = world
    story.db.close()
    with job_lock(story.engine, uuid.uuid4()) as acquired:
        assert acquired
        with pytest.raises(SnapshotError, match="worker"):
            backup(story.engine, tmp_path / "snapshot")


def test_corrupted_deletion_ledger_cannot_silently_skip_an_erasure(world, target, tmp_path, monkeypatch):  # noqa: F811
    import json

    from app.services.works.deletion import execute_purge

    clients, story, ids, *_ = world
    story.db.close()
    archive, ledger = tmp_path / "snapshot", tmp_path / "latest.json"
    backup(story.engine, archive)
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
    execute_purge(ids["work_id"])
    export_deletions(story.engine, ledger)
    data = json.loads(ledger.read_bytes())
    data["deletions"][0]["owner_id"] = str(uuid.uuid4())
    ledger.write_text(json.dumps(data))  # valid JSON, but the deletion would otherwise be silently skipped
    new_roots(monkeypatch, tmp_path)
    with pytest.raises(SnapshotError, match="ledger integrity"):
        restore(target, archive, ledger)
    assert inspect(target).get_table_names() == []


def test_interrupted_restore_keeps_api_and_workers_offline(world, target, tmp_path, monkeypatch):  # noqa: F811
    from app import operations
    from app.core.storage import restore_marker
    from app.db.session import configured_engine

    _, story, ids, *_ = world
    story.db.close()
    archive, ledger = tmp_path / "snapshot", tmp_path / "latest.json"
    backup(story.engine, archive)
    export_deletions(story.engine, ledger)
    new_roots(monkeypatch, tmp_path)
    def interrupted(_):
        raise SnapshotError("synthetic recovery interruption")
    monkeypatch.setattr(operations, "recover_ingestions", interrupted)
    with pytest.raises(SnapshotError, match="interruption"):
        restore(target, archive, ledger)
    assert restore_marker().exists()
    with Session(target) as db:
        assert db.get(Work, uuid.UUID(ids["work_id"])) is not None
    monkeypatch.setenv("DATABASE_URL", target.url.render_as_string(hide_password=False))
    assert configured_engine() is None  # worker entry points fail before claiming or calling a provider
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.get("/health/ready").status_code == 503
        assert client.get("/v1/works").status_code == 503


@pytest.mark.parametrize("render_status", ["queued", "running"])
def test_restored_interrupted_jobs_reconcile_without_rebilling_and_restart_in_a_real_worker(
        world, target, tmp_path, monkeypatch, render_status):  # noqa: F811
    import os
    import subprocess
    import time
    from datetime import UTC, datetime
    from pathlib import Path

    from app.models.entities import Entity
    from app.models.jobs import Job
    from app.models.model_runs import Derivation
    from app.models.narrative_jobs import NarrativeJob
    from app.models.passages import Passage
    from app.models.renders import RenderJob
    from app.models.works import IngestionJob
    from app.services.dispatch import (
        dispatch_ingestions,
        dispatch_narratives,
        dispatch_pending,
    )
    from app.services.visualization import render
    from sqlalchemy import func

    redis = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis:
        pytest.skip("Set VISION_TEST_REDIS_URL for restored worker acceptance")
    clients, story, ids, _, _, extra = world
    probe_id = uuid.UUID(extra["probe"])
    accepted = clients["reader"].post("/v1/works", data={"title": "Interrupted", "format": "txt"},
        files={"file": ("recovery.txt", b"Chapter 1\n\nAn immutable recovery source.")},
        headers={"Origin": "http://127.0.0.1:3000", "Idempotency-Key": "restore-interrupted"}).json()
    job_id = uuid.UUID(accepted["job"]["id"])
    story.db.close()
    with Session(story.engine) as db, db.begin():
        db.get(Job, probe_id).dispatched_at = datetime.now(UTC)  # the old Redis publication is not in the archive
        narrative = db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == story.generation))
        narrative.status, narrative.attempts, narrative.dispatched_at = "running", 1, datetime.now(UTC)
        narrative_id = narrative.id
        entity_query = select(Entity.id).join(Derivation, Derivation.id == Entity.derivation_id).where(
            Derivation.generation_id == story.generation)
        entity_ids = set(db.scalars(entity_query))
        job = db.get(IngestionJob, job_id)
        job.status, job.attempts = "running", 1
        original = db.get(RenderJob, uuid.UUID(ids["job_id"]))
        interrupted = RenderJob(**{key: getattr(original, key) for key in (
            "owner_id", "work_id", "visualization_id", "specification_revision", "specification",
            "specification_sha256", "request_hash", "provider", "model")},
            idempotency_key="interrupted-image", status=render_status,
            started_at=datetime.now(UTC) if render_status == "running" else None)
        db.add(interrupted)
        db.flush()
        render_id = interrupted.id
    archive, ledger = tmp_path / "snapshot", tmp_path / "latest.json"
    started = time.monotonic()
    backup(story.engine, archive)
    export_deletions(story.engine, ledger)
    new_roots(monkeypatch, tmp_path)
    restore(target, archive, ledger)
    print(f"Backup and restore drill: {time.monotonic() - started:.2f}s")
    monkeypatch.setenv("DATABASE_URL", target.url.render_as_string(hide_password=False))
    monkeypatch.setenv("REDIS_URL", redis)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "restore_" + uuid.uuid4().hex)
    with Session(target) as db:
        assert db.get(IngestionJob, job_id).status == "queued"
        assert db.get(RenderJob, render_id).status == "acceptance_unknown"
        assert db.get(Job, probe_id).dispatched_at is None
        assert db.get(NarrativeJob, narrative_id).status == "queued"
    monkeypatch.setattr(render, "image_adapter", lambda: pytest.fail("Recovery attempted a paid provider call"))
    render.execute_render(str(render_id))
    assert dispatch_ingestions(target, job_id) == 1
    assert dispatch_pending(target, probe_id) == 1
    assert dispatch_narratives(target, narrative_id) == 1
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    monkeypatch.setenv("VISION_TEST_WORKSPACE", "1")
    monkeypatch.setenv("VISION_TEST_PARSE_GATE", str(tmp_path / "unused-parse-gate"))
    api = Path(__file__).parents[1]
    with (tmp_path / "restored-worker.log").open("w") as log:
        worker = subprocess.Popen([str(api / ".venv/bin/dramatiq"), "tests.browser_worker", "--processes", "1",
            "--threads", "1", "--queues", "ingestion", "probes", "narrative"], cwd=api, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with Session(target) as db:
                    job = db.get(IngestionJob, job_id)
                    probe = db.get(Job, probe_id)
                    narrative = db.get(NarrativeJob, narrative_id)
                    if job.status in {"failed", "succeeded"} and probe.status == "succeeded" and \
                            narrative.status in {"failed", "succeeded"}:
                        assert (job.status, job.attempts) == ("succeeded", 2)
                        assert (probe.result, probe.attempts) == (2, 1)
                        assert (narrative.status, narrative.attempts) == ("succeeded", 2)
                        document_id = job.document_id
                        break
                time.sleep(0.1)
            else:
                pytest.fail("Restored worker failed to complete interrupted ingestion")
        finally:
            worker.terminate()
            worker.wait(timeout=15)
    from app.services.ingestion.parse import execute_ingestion
    execute_ingestion(str(job_id))  # a stale message cannot republish passages
    with Session(target) as db:
        assert db.scalar(select(func.count()).select_from(Passage).where(Passage.document_id == document_id)) == 1
        assert db.get(RenderJob, render_id).status == "acceptance_unknown"
        assert set(db.scalars(entity_query)) == entity_ids
