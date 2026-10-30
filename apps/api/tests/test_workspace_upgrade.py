"""Legacy ownership and bounded trusted-operator recovery, with real storage."""
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import LoginSession, Principal
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture
def legacy(database, monkeypatch):
    monkeypatch.setenv("VISION_WORKSPACE_SECRET", secrets.token_hex(32))
    with Session(database) as db:
        owner = Principal(username="legacy_reader", password_hash=hash_password("synthetic legacy recovery passphrase"), render_reservations_used=4)
        db.add(owner)
        db.commit()
        db.refresh(owner)
        return create_app(), owner.id


def redeem(client, token, key):
    return client.post("/v1/auth/workspace/recover", headers={**ORIGIN, "Recovery-Key": token, "Idempotency-Key": key})


def test_valid_legacy_cookie_upgrades_same_owner_and_preserves_spend(legacy, database):
    app, owner_id = legacy
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "legacy_reader", "password": "synthetic legacy recovery passphrase"}, headers=ORIGIN).status_code == 200
        result = client.post("/v1/auth/workspace", headers={**ORIGIN, "Idempotency-Key": secrets.token_urlsafe(32)})
        assert result.json()["id"] == str(owner_id)
    with Session(database) as db:
        assert db.get(Principal, owner_id).render_reservations_used == 4


def test_operator_recovery_replays_only_the_same_redemption_and_preserves_owner(legacy, database):
    from app.services.workspace_sessions import issue_recovery
    app, owner_id = legacy
    with Session(database) as db:
        token = issue_recovery(db, owner_id)
    key = secrets.token_urlsafe(32)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        result = redeem(client, token, key)
        assert result.status_code == 200 and result.json()["id"] == str(owner_id)
        client.cookies.clear()
        assert redeem(client, token, key).json()["id"] == str(owner_id)
        assert redeem(client, token, secrets.token_urlsafe(32)).status_code == 401
        assert client.get("/v1/auth/me").json()["id"] == str(owner_id)
    with Session(database) as db:
        assert db.get(Principal, owner_id).render_reservations_used == 4
        assert len(list(db.scalars(select(LoginSession)))) == 1


def test_recovery_rejects_expiry_forgery_and_a_different_active_workspace(legacy, database):
    from app.models.access import WorkspaceRecovery
    from app.services.workspace_sessions import issue_recovery
    app, owner_id = legacy
    with Session(database) as db:
        token = issue_recovery(db, owner_id)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert redeem(client, secrets.token_urlsafe(32), secrets.token_urlsafe(32)).status_code == 401
        anonymous = client.post("/v1/auth/workspace", headers={**ORIGIN, "Idempotency-Key": secrets.token_urlsafe(32)}).json()["id"]
        assert redeem(client, token, secrets.token_urlsafe(32)).status_code == 409
        assert client.get("/v1/auth/me").json()["id"] == anonymous
        client.cookies.clear()
        with Session(database) as db:
            db.scalar(select(WorkspaceRecovery)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        assert redeem(client, token, secrets.token_urlsafe(32)).status_code == 401
