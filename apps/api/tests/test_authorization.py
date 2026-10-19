import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from app.core.passwords import hash_password
from app.core.security import ActorScope, current_actor, database_session, owned_object
from app.main import create_app
from app.models.access import Base, LoginSession, Principal
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, Session, mapped_column

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
PASSWORD = "synthetic local test passphrase"


class OwnedProbe(Base):
    __tablename__ = "test_owned_probe"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"))


@pytest.fixture
def setup(database):
    app = create_app()
    OwnedProbe.__table__.create(database)
    with Session(database) as db:
        first = Principal(username="alice", password_hash=hash_password(PASSWORD))
        second = Principal(username="bruno", password_hash=hash_password(PASSWORD))
        db.add_all([first, second])
        db.flush()
        a, b = OwnedProbe(owner_id=first.id), OwnedProbe(owner_id=second.id)
        db.add_all([a, b])
        db.flush()
        result = first.id, second.id, a.id, b.id
        db.commit()

    @app.get("/_test/owned/{object_id}")
    def probe(
        object_id: uuid.UUID,
        actor: Annotated[ActorScope, Depends(current_actor)],
        db: Annotated[Session, Depends(database_session)],
    ):
        return {"id": str(owned_object(db, OwnedProbe, object_id, actor).id)}

    return app, result


def login(client, username="alice", password=PASSWORD):
    return client.post(
        "/v1/auth/login",
        json={"username": username, "password": password},
        headers=ORIGIN,
    )


def test_two_principals_have_real_scoped_lookups(setup):
    app, (alice, bruno, a, b) = setup
    with (
        TestClient(app, base_url="http://127.0.0.1") as first,
        TestClient(app, base_url="http://127.0.0.1") as second,
    ):
        assert login(first).status_code == 200
        assert login(second, "bruno").status_code == 200
        assert first.get(f"/_test/owned/{a}").status_code == 200
        assert second.get(f"/_test/owned/{b}").status_code == 200
        assert first.get(f"/_test/owned/{b}").status_code == 404
        assert second.get(f"/_test/owned/{a}").status_code == 404
        assert first.get(f"/_test/owned/{uuid.uuid4()}").status_code == 404
        assert first.get("/v1/auth/me", headers={"X-Owner-Id": str(bruno)}).json()[
            "id"
        ] == str(alice)
        assert first.get("/v1/auth/me").headers["cache-control"] == "no-store"


def test_session_expiry_logout_and_cookie_flags(setup, database):
    app, (alice, _, _, _) = setup
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/v1/auth/me").status_code == 401
        response = login(client)
        header = response.headers["set-cookie"].lower()
        assert "httponly" in header and "samesite=strict" in header
        with Session(database) as db:
            record = db.scalar(
                select(LoginSession).where(LoginSession.owner_id == alice)
            )
            assert len(record.token_hash) == 64
            record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        assert client.get("/v1/auth/me").status_code == 401
        assert login(client).status_code == 200
        assert client.post("/v1/auth/logout", headers=ORIGIN).status_code == 204
        assert client.get("/v1/auth/me").status_code == 401


def test_credentials_origin_and_validation_fail_safely(setup):
    app, _ = setup
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert login(client, "unknown").status_code == 401
        assert login(client, password="wrong test passphrase").status_code == 401
        assert (
            client.post(
                "/v1/auth/login", json={"username": "alice", "password": PASSWORD}
            ).status_code
            == 403
        )
        response = client.post(
            "/v1/auth/login",
            json={"username": "alice", "password": PASSWORD, "owner_id": "invented"},
            headers=ORIGIN,
        )
        assert response.status_code == 422
        assert PASSWORD not in response.text
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_login_attempts_have_a_process_bound(setup):
    app, _ = setup
    with TestClient(app, base_url="http://127.0.0.1") as client:
        for _ in range(10):
            assert login(client, "unknown").status_code == 401
        assert login(client, "unknown").status_code == 429


def test_local_cli_provisions_an_account_without_public_registration(database):
    import subprocess
    import sys
    from pathlib import Path

    command = [
        sys.executable,
        "-m",
        "app.cli",
        "create-user",
        "reader",
        "--password-stdin",
    ]
    result = subprocess.run(
        command,
        input=PASSWORD + "\n",
        text=True,
        capture_output=True,
        cwd=Path(__file__).parents[1],
        check=False,
    )
    assert result.returncode == 0
    assert PASSWORD not in result.stdout + result.stderr
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert login(client, "reader").status_code == 200
        assert client.get("/v1/auth/me").json()["username"] == "reader"
        assert client.post("/v1/auth/register", json={}).status_code == 404
