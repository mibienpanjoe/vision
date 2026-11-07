"""Explicit generation reserves one render per prompt version; nothing else reserves; images keep their version."""
import pytest
from app.models.renders import RenderJob
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.test_conversation_turns import post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def renders(story):
    with Session(story.engine) as db:
        return db.scalar(select(func.count()).select_from(RenderJob))


def test_one_render_per_card_revision_from_button_chat_and_retries(api, monkeypatch, tmp_path):
    client, thread, story, _ = setup(api, monkeypatch)
    monkeypatch.setenv("VISION_RENDER_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "synthetic-unused-token")  # reservations only; no provider call runs here
    base = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            post(client, base + "/turns", {"text": "Arthur after the war at home"}, "first", 1)
            first = settled(client, thread["id"])
            assert renders(story) == 0  # upload and prompt composition never reserve
            clicked = post(client, base + "/renders", {"card_revision": 1}, "click-1")
            assert clicked.status_code == 202, clicked.text
            again = post(client, base + "/renders", {"card_revision": 1}, "click-2")  # duplicate click / reload
            assert again.json()["render"]["id"] == clicked.json()["render"]["id"] and renders(story) == 1
            post(client, base + "/turns", {"text": "generate an image"}, "ask-image", first["revision"])
            asked = settled(client, thread["id"])
            assert renders(story) == 1 and asked["card"]["revision"] == 1
            styled_turn = post(client, base + "/turns", {"text": "as a charcoal sketch"}, "style", asked["revision"])
            assert styled_turn.status_code == 202
            styled = settled(client, thread["id"])
            assert renders(story) == 1  # a style edit never generates
            assert post(client, base + "/renders", {"card_revision": 1}, "old").status_code == 409
            fresh = post(client, base + "/renders", {"card_revision": styled["card"]["revision"]}, "click-3")
            assert fresh.status_code == 202 and renders(story) == 2
        finally:
            stop(worker)
    page = client.get(base + "/renders").json()
    assert page["current_card_revision"] == 2
    assert [(item["card_revision"], item["render"]["specification_revision"]) for item in page["items"]] == [(2, 2), (1, 1)]
    messages = [m["content"] for m in client.get(base + "/messages").json()["items"] if m["role"] == "assistant"]
    assert "Generating an image from prompt version 1." in messages
