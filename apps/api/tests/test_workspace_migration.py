"""Snapshot/upgrade a disposable legacy database and retain originals and owner allowance."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.main import create_app
from app.models.works import Work
from app.operations import digest
from app.services.ingestion.parse import execute_ingestion
from app.services.workspace_upgrade import fingerprint, upgrade_workspace
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.test_workspace_upgrade import ORIGIN, legacy  # noqa: F401

pytestmark = pytest.mark.integration


def test_local_operator_snapshots_before_upgrade_and_preserves_book_and_owner(legacy, database, monkeypatch, tmp_path):  # noqa: F811
    app, owner = legacy
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    monkeypatch.setenv("VISION_RENDER_ROOT", str(tmp_path / "renders"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    source = "A synthetic book with a fox 🦊 and e\u0301.\n\nLena wore a blue coat.".encode()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "legacy_reader", "password": "synthetic legacy recovery passphrase"}, headers=ORIGIN).status_code == 200
        accepted = client.post("/v1/works", data={"title": "Legacy book", "format": "txt"}, files={"file": ("old.txt", source)}, headers={**ORIGIN, "Idempotency-Key": "legacy-book"}).json()
        execute_ingestion(accepted["job"]["id"])
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0026")
    with Session(database) as db:
        before = fingerprint(db, owner)
        work = db.scalar(select(Work))
        work_id = work.id
    archive, link = tmp_path / "snapshot", tmp_path / "recovery.url"
    assert upgrade_workspace(database, archive, link, "legacy_reader") == owner
    assert (archive / "database.dump").stat().st_size > 0
    assert (archive / "manifest.json").is_file()
    assert link.stat().st_mode & 0o777 == 0o600
    token = link.read_text().strip().split("#recover=")[1]
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.post("/v1/auth/workspace/recover", headers={**ORIGIN, "Recovery-Key": token, "Idempotency-Key": "synthetic-recovery-request-key-000000"})
        assert response.json()["id"] == str(owner)
        assert client.get(f"/v1/works/{work_id}/original").content == source
    with Session(database) as db:
        assert fingerprint(db, owner) == before
    import json
    manifest = json.loads((archive / "manifest.json").read_text())
    assert manifest["schema"] == "0026" and manifest["database_sha256"] == digest(archive / "database.dump")
