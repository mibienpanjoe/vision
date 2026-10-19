import os
import uuid

import pytest
from app.core.passwords import hash_password
from app.core.storage import PrivateSources
from app.main import create_app
from app.models.access import Principal
from app.models.works import Document, IngestionJob, Work
from app.services.ingestion.reconcile import reconcile_originals
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
PASSWORD = "synthetic source test passphrase"


@pytest.fixture
def readers(database, monkeypatch, tmp_path):
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    with Session(database) as db:
        db.add_all([Principal(username=name, password_hash=hash_password(PASSWORD)) for name in ("upload_alice", "upload_bruno")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as first, TestClient(create_app(), base_url="http://127.0.0.1") as second:
        for client, name in [(first, "upload_alice"), (second, "upload_bruno")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": PASSWORD}, headers=ORIGIN).status_code == 200
        yield first, second


def upload(client, key="source-one", data=b"The captain wore a blue coat.", **params):
    return client.post("/v1/works", data={"title": "Captain", "format": "txt", **params},
                       files={"file": ("../../ignored-name.txt", data, "text/plain")},
                       headers={**ORIGIN, "Idempotency-Key": key})


def test_real_upload_original_library_pagination_and_owner_denials(readers, database):
    alice, bruno = readers
    data = "é🦊é\r\nThe captain wore blue.".encode()
    response = upload(alice, data=data)
    assert response.status_code == 202, response.text
    item = response.json()
    work_id, document_id = item["work"]["id"], item["work"]["document_id"]
    assert item["job"]["status"] == "queued" and item["job"]["dispatch_pending"]
    assert alice.get(f"/v1/works/{work_id}").json() == item["work"]
    original = alice.get(f"/v1/works/{work_id}/original")
    assert original.content == data and "attachment" in original.headers["content-disposition"]
    assert "storage" not in response.text and "source_ref" not in response.text
    with Session(database) as db:
        document = db.get(Document, uuid.UUID(document_id))
        assert PrivateSources().read(document.source_ref) == data
        assert db.get(IngestionJob, uuid.UUID(item["job"]["id"])).document_id == document.id
    upload(alice, key="source-two", title="Second")
    page = alice.get("/v1/works", params={"limit": 1}).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    following = alice.get("/v1/works", params={"limit": 1, "after": page["next_cursor"]}).json()
    assert len(following["items"]) == 1 and following["items"][0]["id"] != page["items"][0]["id"]
    assert following["next_cursor"] is None
    assert bruno.get("/v1/works").json()["items"] == []
    for path in (f"/v1/works/{work_id}", f"/v1/works/{work_id}/original", f"/v1/works/{work_id}/ingestions/{item['job']['id']}"):
        assert bruno.get(path).status_code == 404
    assert alice.get("/v1/works", params={"limit": 101}).status_code == 422
    assert alice.get("/v1/works", params={"after": "bad"}).status_code == 422


def test_upload_replay_conflict_and_original_count(readers, database):
    alice, bruno = readers
    first = upload(alice).json()
    assert upload(alice).json() == first
    assert upload(alice, data=b"different").status_code == 409
    assert upload(alice, title="Changed").status_code == 409
    assert upload(bruno).status_code == 202
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Work)) == 2
        assert db.scalar(select(func.count()).select_from(Document)) == 2
        assert db.scalar(select(func.count()).select_from(IngestionJob)) == 2
    assert len(list(PrivateSources().root.iterdir())) == 2


def test_invalid_oversized_unauthorized_and_origin_inputs_leave_no_sources(readers, database):
    alice, _ = readers
    for data in (b"", b"\xff", b"hello\x00", b"%PDF-1.7\nnot text"):
        assert upload(alice, data=data).status_code == 422
    assert upload(alice, data=b"x" * (8 * 1024 * 1024 + 1)).status_code == 413
    assert upload(alice, format="epub").status_code == 422
    assert upload(alice, title="x" * 257).status_code == 422
    assert upload(alice, owner_id=str(uuid.uuid4())).status_code == 400
    assert alice.post("/v1/works?title=Captain&format=txt", content=b"valid", headers={"Idempotency-Key": "bad-origin"}).status_code == 403
    with TestClient(create_app(), base_url="http://127.0.0.1") as anonymous:
        assert upload(anonymous).status_code == 401
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Work)) == 0
    assert list(PrivateSources().root.iterdir()) == []


def test_filesystem_failure_and_sql_failure_leave_recoverable_state(readers, database, monkeypatch):
    alice, _ = readers
    from app.core.storage import SourceLease
    from sqlalchemy.exc import OperationalError

    original_finish = SourceLease.finish
    def fail_finish(self):
        raise OSError("synthetic private path must not leak")
    monkeypatch.setattr(SourceLease, "finish", fail_finish)
    response = upload(alice)
    assert response.status_code == 503 and "synthetic" not in response.text
    assert list(PrivateSources().root.iterdir()) == []
    monkeypatch.setattr(SourceLease, "finish", original_finish)
    original_commit = Session.commit
    def fail_commit(self):
        raise OperationalError("synthetic", None, Exception("private"))
    monkeypatch.setattr(Session, "commit", fail_commit)
    response = upload(alice)
    assert response.status_code == 503 and "private" not in response.text
    monkeypatch.setattr(Session, "commit", original_commit)
    store = PrivateSources()
    # An uncertain commit retains the opaque file; reconciliation proves it
    # unreferenced before deletion, rather than risking a committed original.
    for path in store.root.iterdir():
        os.utime(path, (0, 0))
    reconcile_originals(database, store)
    assert list(store.root.iterdir()) == []
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Work)) == 0


def test_reconciliation_preserves_linked_and_inflight_originals(readers, database):
    alice, _ = readers
    upload(alice)
    store = PrivateSources()
    linked = list(store.root.iterdir())[0]
    os.utime(linked, (0, 0))
    with store.create() as active:
        active.write(b"active")
        active.finish()
        os.utime(store.path(active.reference), (0, 0))
        assert reconcile_originals(database, store) == 0
        assert store.path(active.reference).exists()
    assert reconcile_originals(database, store) == 1
    assert linked.exists()


def test_uncertain_successful_commit_preserves_original_and_replays(readers, database, monkeypatch):
    alice, _ = readers
    from sqlalchemy.exc import OperationalError

    original_commit = Session.commit
    def lose_acknowledgement(self):
        original_commit(self)
        raise OperationalError("commit acknowledgement lost", None, Exception("synthetic"))
    monkeypatch.setattr(Session, "commit", lose_acknowledgement)
    assert upload(alice).status_code == 503
    monkeypatch.setattr(Session, "commit", original_commit)
    replay = upload(alice)
    assert replay.status_code == 202
    work_id = replay.json()["work"]["id"]
    store = PrivateSources()
    for path in store.root.iterdir():
        os.utime(path, (0, 0))
    assert reconcile_originals(database, store) == 0
    assert alice.get(f"/v1/works/{work_id}/original").status_code == 200


def test_multipart_controls_and_actual_body_size_without_content_length(readers):
    alice, _ = readers
    response = alice.post("/v1/works", data={"title": "é🦊", "format": "md"},
                          files={"file": ("book.md", b"# A heading\n\nBlue coat.", "text/markdown")},
                          headers={**ORIGIN, "Idempotency-Key": "markdown"})
    assert response.status_code == 202 and response.json()["work"]["title"] == "é🦊"
    assert alice.post("/v1/works", data={"title": "Captain", "format": "txt"},
                      files=[("file", ("a.txt", b"a")), ("file", ("b.txt", b"b"))],
                      headers={**ORIGIN, "Idempotency-Key": "two-files"}).status_code == 400
    assert alice.post("/v1/works", content=iter([b"x" * 65536] * 130),
                      headers={**ORIGIN, "Idempotency-Key": "chunked", "Content-Type": "multipart/form-data; boundary=x"}).status_code == 413
    assert alice.post("/v1/works", content=b"not multipart",
                      headers={**ORIGIN, "Idempotency-Key": "bad-type", "Content-Type": "application/octet-stream"}).status_code == 415
