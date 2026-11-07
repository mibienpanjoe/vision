"""Real private workspace bootstrap; no shared owner and no browser-visible credential."""
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import COOKIE_NAME
from app.main import create_app
from app.models.access import LoginSession, Principal
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture
def workspace_app(database, monkeypatch):
    monkeypatch.setenv("VISION_WORKSPACE_SECRET", secrets.token_hex(32))
    return create_app()


def bootstrap(client, key=None):
    return client.post("/v1/auth/workspace", headers={**ORIGIN, "Idempotency-Key": key or secrets.token_urlsafe(32)})


def test_bootstrap_replays_after_lost_response_without_a_second_owner(workspace_app, database):
    key = secrets.token_urlsafe(32)
    with TestClient(workspace_app, base_url="http://127.0.0.1") as first:
        result = bootstrap(first, key)
        assert result.status_code == 200
        cookie = result.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=7776000" in cookie
        owner = result.json()["id"]
    with TestClient(workspace_app, base_url="http://127.0.0.1") as retry:
        assert bootstrap(retry, key).json()["id"] == owner
        assert retry.get("/v1/auth/me").json()["id"] == owner
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Principal)) == 1
        assert db.scalar(select(func.count()).select_from(LoginSession)) == 1


def test_parallel_initialization_reuses_one_workspace(workspace_app, database):
    key = secrets.token_urlsafe(32)
    def send(_):
        with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
            return bootstrap(client, key).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(send, range(2)))) == 1
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Principal)) == 1


def test_separate_contexts_are_distinct_and_invalid_cookie_cannot_claim_legacy(workspace_app, database):
    with TestClient(workspace_app, base_url="http://127.0.0.1") as first, TestClient(workspace_app, base_url="http://127.0.0.1") as other:
        a, b = bootstrap(first).json()["id"], bootstrap(other).json()["id"]
        assert a != b
        first.cookies.set(COOKIE_NAME, "invalid")
        assert bootstrap(first).status_code == 401
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Principal)) == 2


def test_resume_preserves_owner_allowance_and_expired_session_fails_closed(workspace_app, database):
    with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
        owner = bootstrap(client).json()["id"]
        with Session(database) as db:
            principal = db.scalar(select(Principal))
            principal.render_reservations_used = 4
            db.commit()
        assert bootstrap(client).json()["id"] == owner
        with Session(database) as db:
            assert db.scalar(select(Principal)).render_reservations_used == 4
            db.scalar(select(LoginSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        assert bootstrap(client).status_code == 401
        assert client.get("/v1/auth/me").status_code == 401


def test_bootstrap_requires_origin_and_key_and_configured_secret(workspace_app, monkeypatch):
    with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/workspace", headers={"Idempotency-Key": secrets.token_urlsafe(32)}).status_code == 403
        assert client.post("/v1/auth/workspace", headers=ORIGIN).status_code == 422
        monkeypatch.delenv("VISION_WORKSPACE_SECRET")
        assert bootstrap(client).status_code == 503


def test_bootstrap_migration_downgrade_preserves_owned_sessions(workspace_app, database):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
        owner = bootstrap(client).json()["id"]
        command.downgrade(config, "0026")
        assert "workspace_bootstraps" not in inspect(database).get_table_names()
        assert client.get("/v1/auth/me").json()["id"] == owner
        command.upgrade(config, "head")
        assert bootstrap(client).json()["id"] == owner


def test_expired_initialization_receipt_does_not_create_or_reassign_a_workspace(workspace_app, database):
    from app.models.access import WorkspaceBootstrap

    key = secrets.token_urlsafe(32)
    with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
        owner = bootstrap(client, key).json()["id"]
        with Session(database) as db:
            db.scalar(select(WorkspaceBootstrap)).replay_until = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        client.cookies.clear()
        assert bootstrap(client, key).status_code == 401
        with Session(database) as db:
            assert str(db.scalar(select(Principal)).id) == owner


def test_client_supplied_owner_is_rejected(workspace_app, database):
    with TestClient(workspace_app, base_url="http://127.0.0.1") as client:
        response = client.post("/v1/auth/workspace", json={"owner_id": "legacy"},
                               headers={**ORIGIN, "Idempotency-Key": secrets.token_urlsafe(32)})
        assert response.status_code == 422
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Principal)) == 0
