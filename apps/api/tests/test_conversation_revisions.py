"""One evolving card: concise receipts, immutable history, exact guards for concurrent and replayed edits."""
import pytest
from tests.test_conversation_turns import post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def test_card_history_receipts_and_concurrent_edit_guards(api, monkeypatch, tmp_path):
    client, thread, _, _ = setup(api, monkeypatch)
    base = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            post(client, base + "/turns", {"text": "Arthur after the war at home"}, "first", 1)
            first = settled(client, thread["id"])
            # Two tabs at the same revision: the second submission is stale, not silently applied.
            assert post(client, base + "/turns", {"text": "as a charcoal sketch"}, "tab-a", first["revision"]).status_code == 202
            assert post(client, base + "/turns", {"text": "as an oil painting"}, "tab-b", first["revision"]).status_code == 412
            # A lost response retried with the same key and payload returns the same turn; a changed payload conflicts.
            replay = post(client, base + "/turns", {"text": "as a charcoal sketch"}, "tab-a", first["revision"])
            assert replay.status_code == 202
            assert post(client, base + "/turns", {"text": "as watercolour"}, "tab-a", first["revision"]).status_code == 409
            styled = settled(client, thread["id"])
            war = next(v for v in styled["card"]["variants"] if v["label"] == "war")
            post(client, base + "/variant-selections", {"variant_id": war["id"], "card_revision": styled["card"]["revision"]}, "war", styled["revision"])
            moved = settled(client, thread["id"])
        finally:
            stop(worker)
    assistant = [m["content"] for m in client.get(base + "/messages").json()["items"] if m["role"] == "assistant"]
    assert assistant == ["Your source-grounded prompt is ready.", "Restyled: charcoal sketch. Book facts unchanged.",
                         "Updated from the book: war."]
    history = client.get(base + "/cards").json()["items"]
    assert [(item["revision"], item["current"]) for item in history] == [(3, True), (2, False), (1, False)]
    assert history[2]["prompt"] == first["card"]["prompt"] and history[1]["prompt"] == styled["card"]["prompt"]
    assert history[0]["prompt"] == moved["card"]["prompt"] and history[0]["resolved_moment"] == "war"
    # Earlier versions stay immutable and readable by number.
    assert client.get(base + "/cards/1").json()["prompt"] == first["card"]["prompt"]
