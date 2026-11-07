"""One-click variant selection: verified replacement, replay, stale and forged actions, no image reservation."""
import pytest
from app.models.renders import RenderJob
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.test_conversation_turns import post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def test_selecting_a_variant_reconstructs_verifies_and_keeps_the_prior_prompt(api, monkeypatch, tmp_path):
    client, thread, story, _ = setup(api, monkeypatch)
    base = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            post(client, base + "/turns", {"text": "Arthur after the war at home"}, "first", 1)
            first = settled(client, thread["id"])
            card = first["card"]
            war = next(v for v in card["variants"] if v["label"] == "war")
            body = {"variant_id": war["id"], "card_revision": card["revision"]}
            assert post(client, base + "/variant-selections", {**body, "variant_id": "variant:" + "0" * 16}, "forged", first["revision"]).status_code == 409
            assert post(client, base + "/variant-selections", {**body, "card_revision": 9}, "stale-card", first["revision"]).status_code == 409
            assert post(client, base + "/variant-selections", {"variant_id": "../x", "card_revision": 1}, "bad", first["revision"]).status_code == 422
            assert post(client, base + "/variant-selections", body, "stale-tab", first["revision"] - 1).status_code == 412
            accepted = post(client, base + "/variant-selections", body, "war", first["revision"])
            assert accepted.status_code == 202, accepted.text
            assert post(client, base + "/variant-selections", body, "war", first["revision"]).json()["id"] == accepted.json()["id"]
            during = client.get(base).json()
            assert during["card"]["prompt"] == card["prompt"] or during["card"]["revision"] == card["revision"] + 1
            done = settled(client, thread["id"])
        finally:
            stop(worker)
    assert done["card"]["revision"] == card["revision"] + 1
    assert "steel armor" in done["card"]["prompt"] and done["card"]["specification"]["result"]["data"]["scope"]["resolved_moment"] == "war"
    messages = client.get(base + "/messages").json()["items"]
    assert [m["content"] for m in messages if m["role"] == "user"][-1] == "Show war"
    with Session(story.engine) as db:
        assert db.scalar(select(func.count()).select_from(RenderJob)) == 0
