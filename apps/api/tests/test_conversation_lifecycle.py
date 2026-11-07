"""Deleting a book ends its unfinished turns, waits for running ones and purges every conversation row."""
import pytest
from app.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    PromptCardRevision,
)
from app.models.works import Document
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.test_conversation_turns import ORIGIN, post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def count(engine, model):
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(model))


def test_book_deletion_cancels_turns_and_purges_conversations(api, monkeypatch, tmp_path):
    client, thread, story, redis_url = setup(api, monkeypatch)
    base = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            post(client, base + "/turns", {"text": "Arthur after the war at home"}, "first", 1)
            done = settled(client, thread["id"])
        finally:
            stop(worker)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # the next turn stays queued, undispatched
    queued = post(client, base + "/turns", {"text": "as a charcoal sketch"}, "queued", done["revision"]).json()
    monkeypatch.setenv("REDIS_URL", redis_url)
    work_id = thread["work_id"]
    with Session(story.engine) as db:
        revision = db.scalar(select(Document.revision).where(Document.work_id == work_id))
        from app.services.works.deletion import RUNNING_TURN, active_jobs
        turn = db.get(ConversationTurn, queued["id"])
        turn.status = "composing"  # simulate a running turn: the purge must wait for it
        db.commit()
        assert active_jobs(db, work_id) == 1 and "composing" in RUNNING_TURN
        turn.status = "queued"
        db.commit()
    accepted = client.delete(f"/v1/works/{work_id}", headers={**ORIGIN, "Idempotency-Key": "delete-book", "If-Match": f'"{revision}"'})
    assert accepted.status_code == 202, accepted.text
    with Session(story.engine) as db:
        cancelled = db.get(ConversationTurn, queued["id"])
        assert (cancelled.status, cancelled.error_code) == ("cancelled", "WORK_DELETED")
    assert client.get(base).status_code == 404
    from app.services.works.deletion import execute_purge
    execute_purge(work_id)
    for model in (Conversation, ConversationTurn, ConversationMessage, PromptCardRevision):
        assert count(story.engine, model) == 0, model
    with Session(story.engine) as db:
        assert db.scalar(select(func.count()).select_from(Document).where(Document.work_id == work_id)) == 0
