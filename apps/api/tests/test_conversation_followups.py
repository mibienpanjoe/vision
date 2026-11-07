"""Natural followups resolve from durable conversation state through the real worker and gates."""
import time

import pytest
from app.models.conversations import ConversationTurn
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.test_conversation_turns import post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def test_followups_use_stored_context_typed_intents_and_existing_gates(api, monkeypatch, tmp_path):
    client, thread, story, _ = setup(api, monkeypatch)
    path = f'/v1/conversations/{thread["id"]}/turns'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            revision = 1

            def ask(text, key, expected="succeeded", **extra):
                nonlocal revision
                accepted = post(client, path, {"text": text, **extra}, key, revision)
                assert accepted.status_code == 202, accepted.text
                view = settled(client, thread["id"], expected)
                revision = view["revision"]
                return view

            first = ask("Arthur after the war at home", "first")
            assert first["card"]["revision"] == 1 and "plain linen shirt" in first["card"]["prompt"]
            # A fresh worker proves the followup reads durable state, not process memory.
            stop(worker)
            worker = start(log)
            styled = ask("as a charcoal sketch", "style")
            assert styled["card"]["revision"] == 2
            assert "charcoal sketch" in styled["card"]["prompt"] and "plain linen shirt" in styled["card"]["prompt"]
            kept = ask("keep the clothes", "keep")
            locks = kept["card"]["specification"]["result"]["data"]["locks"]
            assert {(lock["attribute"], lock["value"]) for lock in locks} == {("attire", "plain linen shirt")}
            sources = ask("where does the book say that?", "sources")
            assert sources["card"]["revision"] == kept["card"]["revision"]
            assert sources["active_turn"]["card_revision"] == kept["card"]["revision"]
            forged = post(client, path, {"text": "pick it", "choice": "choice:0"}, "forged", revision)
            assert forged.status_code == 202
            for _ in range(300):
                view = client.get(f'/v1/conversations/{thread["id"]}').json()
                if view["active_turn"]["status"] in {"succeeded", "needs_context", "insufficient_evidence", "failed"}:
                    break
                time.sleep(0.1)
            assert view["card"]["revision"] == kept["card"]["revision"] or view["active_turn"]["status"] == "succeeded"
            assert post(client, path, {"text": "x", "choice": "../../works"}, "bad-choice", view["revision"]).status_code == 422
        finally:
            stop(worker)
    with Session(story.engine) as db:
        turns = list(db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == thread["id"])
                                .order_by(ConversationTurn.created_at)))
        assert [turn.intent["kind"] for turn in turns] == [
            "new_portrayal", "presentation_edit", "presentation_edit", "source_request", "new_portrayal"]
        assert all(turn.intent["version"] == "conversation-intent-v1" and turn.intent["source"] == "deterministic" for turn in turns)
