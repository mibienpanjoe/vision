"""Real SQL/Redis/actor receipts; synthetic text adapters are isolated to the worker fixture."""
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.models.conversations import ConversationMessage
from app.models.generations import SourceGeneration
from app.services.conversations.store import now
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
API = Path(__file__).parents[1]


def post(client, path, body, key, revision=None):
    return client.post(path, json=body, headers={**ORIGIN, "Idempotency-Key": key,
                       **({"If-Match": f'"{revision}"'} if revision else {})})


def setup(api, monkeypatch):
    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Real Redis is required")
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    _, clients, work_id, story = api
    with Session(story.engine) as db, db.begin():
        generation = db.get(SourceGeneration, story.generation)
        generation.narrative_ready_at = generation.search_ready_at = now()
    client = clients["reader"]
    thread = post(client, "/v1/conversations", {"work_id": work_id, "title": "Portrait"}, "thread").json()
    return client, thread, story, redis_url


def start(log):
    return subprocess.Popen([str(API / ".venv/bin/dramatiq"), "tests.conversation_worker", "--processes", "1", "--threads", "1"],
                            cwd=API, env=os.environ.copy(), stdout=log, stderr=log, start_new_session=True)


def stop(worker):
    if worker and worker.poll() is None:
        os.killpg(worker.pid, signal.SIGTERM)
        try:
            worker.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=5)


def settled(client, thread_id, expected="succeeded"):
    for _ in range(300):
        view = client.get(f"/v1/conversations/{thread_id}").json()
        if view["active_turn"]["status"] == expected:
            return view
        time.sleep(0.1)
    pytest.fail(f"Conversation did not reach {expected}")


def test_sql_intent_survives_broker_outage_replay_redelivery_and_restart(api, monkeypatch, tmp_path):
    client, thread, story, redis_url = setup(api, monkeypatch)
    path = f'/v1/conversations/{thread["id"]}/turns'
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    body = {"text": "Arthur after the war at home"}
    accepted = post(client, path, body, "first", 1)
    assert accepted.status_code == 202, accepted.text
    turn = accepted.json()
    assert turn["status"] == "queued" and turn["dispatch_pending"]
    assert post(client, path, body, "first", 1).json()["id"] == turn["id"]
    assert post(client, path, {"text": "Mira"}, "first", 1).status_code == 409
    assert post(client, path, body, "stale", 1).status_code == 412
    assert post(client, path, body, "missing-revision").status_code == 428
    monkeypatch.setenv("REDIS_URL", redis_url)
    from app.services.dispatch import dispatch_conversations
    assert dispatch_conversations(story.engine) == 1
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            result = settled(client, thread["id"])
            assert result["card"]["prompt"] == result["card"]["specification"]["result"]["data"]["generation"]["prompt"]
            stop(worker)
            worker = start(log)
            from app.services.dispatch import configured_broker
            from dramatiq import Message
            broker = configured_broker()
            try:
                broker.enqueue(Message(queue_name="conversation", actor_name="converse", args=(turn["id"],), kwargs={}, options={}))
            finally:
                broker.close()
            time.sleep(1)
            assert client.get(f'/v1/conversations/{thread["id"]}').json()["card"] == result["card"]
            with Session(story.engine) as db:
                from app.models.renders import RenderJob
                assert db.scalar(select(func.count()).select_from(RenderJob)) == 0
                assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 2
        finally:
            stop(worker)


def test_dead_worker_recovery_respects_live_lease_and_publishes_once(api, monkeypatch, tmp_path):
    from app.models.conversations import ConversationTurn
    from app.services.conversations.turns import recover_turns
    from app.services.dispatch import dispatch_conversations
    client, thread, story, _ = setup(api, monkeypatch)
    gate = tmp_path / "pause"
    gate.touch()
    monkeypatch.setenv("VISION_TEST_CONVERSATION_GATE", str(gate))
    turn = post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur after the war at home"}, "first", 1).json()
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            for _ in range(200):
                if gate.with_suffix(".started").exists():
                    break
                time.sleep(0.1)
            assert gate.with_suffix(".started").exists()
            assert client.get(f'/v1/conversations/{thread["id"]}/turns/{turn["id"]}').json()["status"] == "retrieving"
            assert recover_turns(story.engine) == 0
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=5)
            for _ in range(30):
                if recover_turns(story.engine) == 1:
                    break
                time.sleep(0.1)
            gate.unlink()
            assert dispatch_conversations(story.engine) == 1
            worker = start(log)
            result = settled(client, thread["id"])
            assert result["card"]["revision"] == 1
            with Session(story.engine) as db:
                assert db.get(ConversationTurn, uuid.UUID(turn["id"])).attempts == 2
                assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 2
        finally:
            stop(worker)


def test_supersession_and_cancellation_keep_receipts_and_reject_forged_paths(api, monkeypatch):
    client, thread, _, _ = setup(api, monkeypatch)
    monkeypatch.delenv("REDIS_URL", raising=False)
    path = f'/v1/conversations/{thread["id"]}/turns'
    first = post(client, path, {"text": "Arthur"}, "first", 1).json()
    second = post(client, path, {"text": "Mira"}, "second", 2).json()
    assert client.get(f'{path}/{first["id"]}').json()["status"] == "superseded"
    cancel_path = f'{path}/{second["id"]}/cancel'
    assert post(client, cancel_path, {}, "cancel", 2).status_code == 412
    response = post(client, cancel_path, {}, "cancel", 3)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert post(client, cancel_path, {}, "cancel", 3).json() == response.json()
    assert post(client, cancel_path, {}, "changed", 3).status_code == 409
    assert post(client, path, {"text": "Mira"}, "second", 2).json()["id"] == second["id"]
    assert client.get(f'/v1/conversations/{thread["id"]}').json()["card"] is None
    stranger = api[1]["stranger"]
    assert post(stranger, cancel_path, {}, "forged", 3).status_code == 404
    assert post(client, f'{path}/{uuid.uuid4()}/cancel', {}, "forged", 3).status_code == 404


def test_waiting_request_persists_until_real_preparation_is_ready(api, monkeypatch, tmp_path):
    from app.services.conversations.turns import recover_turns
    from app.services.dispatch import dispatch_conversations
    client, thread, story, _ = setup(api, monkeypatch)
    with Session(story.engine) as db, db.begin():
        generation = db.get(SourceGeneration, story.generation)
        generation.narrative_ready_at = None
    response = post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur after the war at home"}, "waiting", 1)
    assert response.status_code == 202
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            settled(client, thread["id"], "waiting_for_book")
            assert recover_turns(story.engine) == 0
            with Session(story.engine) as db, db.begin():
                db.get(SourceGeneration, story.generation).narrative_ready_at = now()
            assert recover_turns(story.engine) == 1
            assert dispatch_conversations(story.engine) == 1
            assert settled(client, thread["id"])["card"] is not None
            messages = client.get(f'/v1/conversations/{thread["id"]}/messages').json()["items"]
            assert [m["content"] for m in messages if m["role"] == "user"] == ["Arthur after the war at home"]
        finally:
            stop(worker)


def test_failed_publication_rolls_back_card_receipt_and_terminal_state_together(api, monkeypatch):
    from app.core.security import ActorScope
    from app.models.access import Principal
    from app.models.conversations import (
        Conversation,
        ConversationTurn,
        PromptCardRevision,
    )
    from app.services.conversations import store
    from tests.test_refinement import stored
    _, _, work_id, story = api
    visualization = stored(api)
    with Session(story.engine) as db, db.begin():
        owner = db.scalar(select(Principal).where(Principal.username == "reader"))
        actor = ActorScope(owner.id, owner.username)
        thread = store.create(db, actor, uuid.UUID(work_id), "Atomic card", "atomic")
        first = store.enqueue(db, actor, thread.id, '"1"', "first", {"text": "Arthur"}, "test")
        store.publish_card(db, first.id, uuid.UUID(visualization["id"]), 1, "Ready.")
        second = store.enqueue(db, actor, thread.id, '"3"', "second", {"text": "Change portrait"}, "test")
        thread_id, turn_id, card_id = thread.id, second.id, thread.card_id
    with pytest.raises(RuntimeError), Session(story.engine) as db, db.begin():
        store.publish_card(db, turn_id, uuid.UUID(visualization["id"]), 1, "Replacement.")
        raise RuntimeError("Fail after all publication writes, before commit")
    with Session(story.engine) as db:
        assert db.get(Conversation, thread_id).card_revision == 1
        assert db.get(ConversationTurn, turn_id).status == "queued"
        assert db.get(PromptCardRevision, (card_id, 2)) is None
        assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 3


def test_restart_after_specification_commit_reuses_exact_result(api, monkeypatch, tmp_path):
    from app.models.visualizations import Visualization
    from app.services.conversations.turns import recover_turns
    from app.services.dispatch import dispatch_conversations
    client, thread, story, _ = setup(api, monkeypatch)
    gate = tmp_path / "publication"
    gate.touch()
    monkeypatch.setenv("VISION_TEST_CARD_GATE", str(gate))
    post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur after the war at home"}, "first", 1)
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            for _ in range(200):
                if gate.with_suffix(".started").exists():
                    break
                time.sleep(0.1)
            assert gate.with_suffix(".started").exists()
            with Session(story.engine) as db:
                assert db.scalar(select(func.count()).select_from(Visualization)) == 1
                assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 1
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=5)
            for _ in range(30):
                if recover_turns(story.engine) == 1:
                    break
                time.sleep(0.1)
            gate.unlink()
            assert dispatch_conversations(story.engine) == 1
            worker = start(log)
            assert settled(client, thread["id"])["card"]["revision"] == 1
            with Session(story.engine) as db:
                assert db.scalar(select(func.count()).select_from(Visualization)) == 1
                assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 2
        finally:
            stop(worker)


def test_reconcile_republishes_old_sql_intent_after_queue_loss(api, monkeypatch):
    from datetime import timedelta

    from app.models.conversations import ConversationTurn
    from app.services.conversations.turns import recover_turns
    from app.services.dispatch import configured_broker, dispatch_conversations
    client, thread, story, _ = setup(api, monkeypatch)
    result = post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur"}, "lost", 1).json()
    broker = configured_broker()
    try:
        broker.flush_all()  # This test's UUID namespace only.
    finally:
        broker.close()
    with Session(story.engine) as db, db.begin():
        db.get(ConversationTurn, uuid.UUID(result["id"])).dispatched_at = now() - timedelta(minutes=6)
    assert recover_turns(story.engine) == 1
    assert dispatch_conversations(story.engine) == 1
