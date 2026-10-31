import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from tests.epub_builder import build
from tests.test_conversation_turns import API, post, setup, stop

pytestmark = pytest.mark.integration
ROOT = Path(__file__).parent / "fixtures"


def upload_worker(log):
    return subprocess.Popen([str(API / ".venv/bin/dramatiq"), "tests.conversation_upload_worker", "--processes", "1", "--threads", "2"],
                            cwd=API, env=os.environ.copy(), stdout=log, stderr=log, start_new_session=True)


def wait(client, path, status, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200
        value = response.json()
        if value["active_turn"]["status"] == status:
            return value
        if value["active_turn"]["status"] in {"failed", "insufficient_evidence", "needs_context", "cancelled", "superseded"}:
            pytest.fail(json.dumps(value["active_turn"]))
        time.sleep(0.1)
    pytest.fail(f"Attachment request did not reach {status}; last status {value['active_turn']['status']}")


@pytest.mark.parametrize("source_format", ["txt", "md", "pdf", "epub"])
def test_attach_and_ask_resumes_automatically_after_real_preparation(api, monkeypatch, tmp_path, source_format):
    client, _, _, _ = setup(api, monkeypatch)
    gate = tmp_path / "parse"
    gate.touch()
    monkeypatch.setenv("VISION_TEST_PARSE_GATE", str(gate))
    monkeypatch.setenv("VISION_TEST_WORKSPACE", "1")
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    if source_format == "epub":
        source = build()
    elif source_format == "pdf":
        source = (ROOT / "formats/story.pdf").read_bytes()
    else:
        source = (ROOT / "narrative/story.md").read_bytes()
    uploaded = client.post("/v1/works", files={"file": (f"book.{source_format}", source)},
                           headers={"Origin": "http://127.0.0.1:3000", "Idempotency-Key": "book"})
    assert uploaded.status_code == 202, uploaded.text
    book = uploaded.json()["work"]
    thread = post(client, "/v1/conversations", {"work_id": book["id"], "title": "Arthur portrait"}, "conversation").json()
    question = "Arthur after the war at home"
    turn = post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": question}, "question", 1)
    assert turn.status_code == 202
    path = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = upload_worker(log)
            waiting = wait(client, path, "waiting_for_book")
            assert waiting["card"] is None
            gate.unlink()
            ready = wait(client, path, "succeeded", seconds=120)
            assert ready["card"]["prompt"] and ready["card"]["specification"]["work_id"] == book["id"]
            messages = client.get(path + "/messages").json()["items"]
            assert [m["content"] for m in messages if m["role"] == "user"] == [question]
            assert client.get(f'/v1/works/{book["id"]}/original').content == source
            assert client.get(path).json()["card"] == ready["card"]
        finally:
            stop(worker)


def test_preparation_completion_during_waiting_lease_is_not_lost(api, monkeypatch):
    import uuid

    from app.models.conversations import ConversationTurn
    from app.models.generations import SourceGeneration
    from app.models.narrative_jobs import NarrativeJob
    from app.services.conversations import turns
    from app.services.conversations.attachments import preparation_finished
    from app.services.conversations.store import now
    from app.services.dispatch import configured_broker
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    client, thread, story, _ = setup(api, monkeypatch)
    accepted = post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur"}, "race", 1).json()
    broker = configured_broker()
    try:
        broker.flush_all()
    finally:
        broker.close()

    def complete_while_leased(engine, turn_id):
        with Session(engine) as db, db.begin():
            db.get(ConversationTurn, turn_id).status = "waiting_for_book"
            generation = db.get(SourceGeneration, story.generation)
            generation.narrative_ready_at = generation.search_ready_at = now()
            job = db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == generation.id))
            job.status = "succeeded"
            job_id = job.id
        preparation_finished(engine, job_id, narrative=True)
        with Session(engine) as db:
            assert db.get(ConversationTurn, turn_id).status == "waiting_for_book"

    monkeypatch.setattr(turns, "execute_claimed", complete_while_leased)
    turns.execute_turn(accepted["id"])
    with Session(story.engine) as db:
        turn = db.get(ConversationTurn, uuid.UUID(accepted["id"]))
        assert turn.status == "queued" and turn.dispatched_at is not None


def test_unsupported_scan_finishes_waiting_request_without_losing_its_message(api, monkeypatch, tmp_path):
    client, _, _, _ = setup(api, monkeypatch)
    gate = tmp_path / "parse"
    gate.touch()
    monkeypatch.setenv("VISION_TEST_PARSE_GATE", str(gate))
    monkeypatch.setenv("VISION_TEST_WORKSPACE", "1")
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    source = (ROOT / "formats/outlined.pdf").read_bytes()
    uploaded = client.post("/v1/works", files={"file": ("book.pdf", source)},
                           headers={"Origin": "http://127.0.0.1:3000", "Idempotency-Key": "scan"}).json()
    thread = post(client, "/v1/conversations", {"work_id": uploaded["work"]["id"]}, "scan-thread").json()
    post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Show Arthur"}, "question", 1)
    path = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = upload_worker(log)
            wait(client, path, "waiting_for_book")
            gate.unlink()
            failed = wait(client, path, "failed")
            assert failed["active_turn"]["error_code"] == "BOOK_PREPARATION_FAILED" and failed["card"] is None
            job = client.get(f'/v1/works/{uploaded["work"]["id"]}/ingestions/{uploaded["job"]["id"]}').json()
            assert job["error_code"] == "TEXT_LAYER_UNAVAILABLE"
            messages = client.get(path + "/messages").json()["items"]
            assert messages[0]["content"] == "Show Arthur"
        finally:
            stop(worker)
