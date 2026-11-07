"""Variants come from the card's own consolidation, for the same subject, with real differences and spans."""
import pytest
from tests.test_conversation_turns import post, settled, setup, start, stop

pytestmark = pytest.mark.integration


def test_variants_are_bounded_evidence_backed_and_bound_to_the_card(api, monkeypatch, tmp_path):
    client, thread, _, _ = setup(api, monkeypatch)
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = start(log)
            assert post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": "Arthur after the war at home"}, "first", 1).status_code == 202
            view = settled(client, thread["id"])
        finally:
            stop(worker)
    card = view["card"]
    variants = card["variants"]
    assert 1 <= len(variants) <= 3
    shown = card["specification"]["result"]["data"]["scope"]["resolved_moment"]
    current = {t["attribute"]: t["values"] for t in card["specification"]["result"]["data"]["subject"]["traits"] if t["status"] == "canonical"}
    for variant in variants:
        assert variant["label"] != shown
        assert variant["card_revision"] == card["revision"] and variant["generation_id"] == card["generation_id"]
        for change in variant["changes"]:
            assert change["after"] != current.get(change["attribute"], [])
            assert change["before"] == current.get(change["attribute"], [])
        for span in variant["evidence"]:
            assert span["quote"] and "Mira" not in span["quote"].split(" held")[0]  # not another character's trait
    assert len({v["id"] for v in variants}) == len(variants)
    # Same card read again issues the same IDs.
    assert [v["id"] for v in client.get(f'/v1/conversations/{thread["id"]}').json()["card"]["variants"]] == [v["id"] for v in variants]
