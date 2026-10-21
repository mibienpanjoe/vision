"""The real compose endpoint over stored source evidence, with deterministic consolidation and adjudication."""

import pytest
from app.main import create_app
from app.providers.contracts import ProviderRateLimited
from app.providers.deterministic import RuleAdapter
from app.schemas.visualization import VisualizationResult
from app.services.visualization import specification
from fastapi.testclient import TestClient
from tests.conftest import ORIGIN
from tests.test_appearance_states import annotated_consolidation

pytestmark = pytest.mark.integration
PASSWORD = "synthetic query plan passphrase"


def outcome(response):
    assert response.status_code == 200, response.text
    VisualizationResult.model_validate_json(response.text)  # schema round trip
    return response.json()


def traits(member):
    return {t["attribute"]: (t["status"], t["values"]) for t in member["traits"]}


def test_resolved_specification_cites_resolvable_in_scope_evidence(api):
    compose, clients, work_id, story = api
    body = outcome(compose(chapter=3, query="Arthur at home after the war"))
    assert body["outcome"] == "resolved"
    spec = body["data"]
    assert spec["spec_version"] == "vision-spec-1.0"
    assert spec["scope"]["through_chapter_id"] == str(story.chapters[3]) and spec["scope"]["resolved_moment"] == "dinner"
    assert traits(spec["subject"]) == {"attire": ("canonical", ["plain linen shirt"]),
                                       "left_cheek": ("canonical", ["scar still visible"])}
    assert {"hair", "eyes"} <= set(spec["subject"]["unknown"])
    assert next(t for t in spec["subject"]["traits"] if t["attribute"] == "attire")["adjudication"] == "entailed"
    assert spec["verification"]["adjudication"] == "applied"
    assert set(spec["lineage"]["processing"]) == {"query_plan", "consolidation", "index", "parser"}
    assert spec["lineage"]["processing"]["index"].startswith("index-v1/deterministic/hashed-v1")
    assert "plain linen shirt" in spec["generation"]["prompt"] and "steel armor" not in spec["generation"]["prompt"]
    assert "steel armor" in spec["generation"]["negative_prompt"]  # removed before dinner
    assert "chestnut" not in spec["generation"]["negative_prompt"]  # childhood hair is unknown here, not ruled out
    boundary = {"mode": "through_chapter", "chapter_id": str(story.chapters[3])}
    for member in [spec["subject"], *spec["participants"], *spec["world"]]:
        for trait in member["traits"]:
            for span in trait["evidence"]:
                resolved = clients["reader"].post(f"/v1/works/{work_id}/evidence", headers=ORIGIN, json={
                    "span": span, "parser_revision": spec["scope"]["parser_revision"], "reading_boundary": boundary})
                assert resolved.status_code == 200, resolved.text


def test_context_choices_and_insufficient_evidence_are_explicit(api):
    compose, *_ = api
    captain = outcome(compose(chapter=2, query="the captain during the war"))
    assert captain["outcome"] == "needs_context"
    assert {(c["field"], c["label"]) for c in captain["choices"]} == {("subject", "Mira (character)"),
                                                                     ("subject", "Brann (character)")}
    moments = outcome(compose(chapter=3, query="Arthur"))
    assert moments["outcome"] == "needs_context" and [c["label"] for c in moments["choices"]] == ["child", "war", "dinner"]
    assert {c["field"] for c in moments["choices"]} == {"moment"}
    assert outcome(compose(chapter=2, query="the dragon"))["outcome"] == "insufficient_evidence"
    unanchored = outcome(compose(chapter=2, query="Arthur in spring"))
    assert unanchored["outcome"] == "insufficient_evidence" and "moment" in unanchored["missing"][0]


def test_provider_failures_are_failed_outcomes_without_fallback(api, monkeypatch):
    compose, *_ = api
    monkeypatch.setattr(specification, "consolidation_adapter",
                        lambda: RuleAdapter(annotated_consolidation, fail=ProviderRateLimited()))
    limited = outcome(compose(chapter=2, query="Arthur during the war"))
    assert limited["outcome"] == "failed"
    assert (limited["error"]["code"], limited["error"]["retryable"]) == ("PROVIDER_RATE_LIMITED", True)
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: None)
    disabled = outcome(compose(chapter=2, query="Arthur during the war"))
    assert (disabled["error"]["code"], disabled["error"]["retryable"]) == ("PROVIDER_NOT_ENABLED", False)


def test_interpretation_adds_labelled_creative_choices_without_changing_canon(api):
    compose, *_ = api
    canon = outcome(compose(chapter=3, query="Arthur at home after the war"))["data"]
    styled = outcome(compose(chapter=3, query="Arthur at home after the war", creative_mode="interpretation",
                             style="sepia ink wash"))["data"]
    assert traits(styled["subject"]) == traits(canon["subject"])
    assert {(c["attribute"], c["value"]) for c in styled["creative"]} == {
        ("style", "sepia ink wash"), ("hair", "artist's choice"), ("eyes", "artist's choice")}
    assert all(c["support"] == "creative" for c in styled["creative"]) and canon["creative"] == []
    assert '"sepia ink wash"' not in styled["generation"]["prompt"] and "sepia ink wash" in styled["generation"]["prompt"]


def test_scene_requests_keep_members_and_place_evidence(api):
    compose, *_ = api
    scene = outcome(compose(chapter=3, query="Arthur at dinner with Mira and Brann"))["data"]
    assert [m["entity"]["label"] for m in scene["participants"]] == ["Élodie", "Mira", "brass compass"]
    assert traits(next(m for m in scene["participants"] if m["entity"]["label"] == "Mira"))["held_object"] == (
        "canonical", ["brass compass"])
    assert {e["label"]: e["reason"] for e in scene["excluded"]}["Brann"] == "absent from this scene"
    # Similarity search reaches "The house's roof was still missing", so the house is present with that roof;
    # "Warm candlelight lit the room" never names the house and stays out.
    house = traits(scene["world"][0])
    assert scene["world"][0]["entity"]["label"] == "house by the ash tree" and scene["unknown"] == []
    assert house["roof"] == ("canonical", ["missing"]) and "lighting" not in house


def test_access_and_request_validation_fail_closed(api):
    compose, clients, work_id, _ = api
    assert compose(client="stranger", query="Arthur").status_code == 404
    assert compose(query="Arthur", story_event_id="later").status_code == 422
    assert compose(creative_mode="canon_first").status_code == 422
    with TestClient(create_app(), base_url="http://127.0.0.1") as anonymous:
        assert anonymous.post(f"/v1/works/{work_id}/visualizations/compose", json={"query": "Arthur"},
                              headers=ORIGIN).status_code == 401


@pytest.mark.skipif(__import__("os").environ.get("VISION_LIVE_GROQ") != "1",
                    reason="Set VISION_LIVE_GROQ=1 and GROQ_API_KEY to compose through Groq")
def test_live_compose_through_groq(api, monkeypatch):
    import json

    from app.providers.openai_compatible import GroqGateway
    compose, *_ = api
    monkeypatch.setattr(specification, "consolidation_adapter", GroqGateway.from_environment)
    monkeypatch.setattr(specification, "adjudicator", lambda adapter: adapter)
    body = outcome(compose(chapter=3, query="Arthur at home after the war"))
    summary = body if body["outcome"] != "resolved" else {
        "moment": body["data"]["scope"]["resolved_moment"], "subject": traits(body["data"]["subject"]),
        "unknown": body["data"]["subject"]["unknown"], "participants": [m["entity"]["label"] for m in body["data"]["participants"]],
        "world": [m["entity"]["label"] for m in body["data"]["world"]], "verification": body["data"]["verification"],
        "prompt": body["data"]["generation"]["prompt"], "negative": body["data"]["generation"]["negative_prompt"]}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    assert body["outcome"] in {"resolved", "needs_context", "insufficient_evidence", "failed"}


def store(api, key, client="reader", chapter=3, **body):
    compose, clients, work_id, story = api
    if chapter is not None:
        body["through_chapter_id"] = str(story.chapters[chapter])
    return clients[client].post(f"/v1/works/{work_id}/visualizations", json=body,
                                headers={**ORIGIN, "Idempotency-Key": key})


def test_resolved_results_are_stored_once_and_read_back_with_history(api):
    compose, clients, work_id, story = api
    reader = clients["reader"]
    created = store(api, "home-1", query="Arthur at home after the war")
    assert created.status_code == 201 and created.headers["ETag"] == '"1"'
    stored = created.json()["visualization"]
    assert created.json()["result"] == stored["result"] and stored["revision"] == 1
    assert stored["request"]["query"] == "Arthur at home after the war"
    replay = store(api, "home-1", query="Arthur at home after the war")
    assert (replay.status_code, replay.json()["visualization"]["id"]) == (201, stored["id"])
    conflict = store(api, "home-1", query="Arthur during the war", chapter=2)
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (409, "IDEMPOTENCY_CONFLICT")
    assert store(api, "home-1", client="stranger", query="Arthur").status_code == 404

    read = reader.get(f"/v1/works/{work_id}/visualizations/{stored['id']}")
    assert (read.status_code, read.headers["ETag"], read.json()) == (200, '"1"', stored)
    page = reader.get(f"/v1/works/{work_id}/visualizations").json()["items"]
    assert [(i["id"], i["subject"], i["revision"]) for i in page] == [(stored["id"], "Arthur", 1)]
    history = reader.get(f"/v1/works/{work_id}/visualizations/{stored['id']}/revisions").json()["items"]
    assert [(r["number"], r["parser_revision"], r["consolidation_id"]) for r in history] == [
        (1, stored["result"]["data"]["scope"]["parser_revision"], stored["result"]["data"]["lineage"]["consolidation_id"])]
    assert reader.get(f"/v1/works/{work_id}/visualizations/{stored['id']}/revisions/1").json() == stored
    assert reader.get(f"/v1/works/{work_id}/visualizations/{stored['id']}/revisions/2").status_code == 404
    for path in ("", "/revisions", "/revisions/1"):
        assert clients["stranger"].get(f"/v1/works/{work_id}/visualizations/{stored['id']}{path}").status_code == 404
    assert clients["stranger"].get(f"/v1/works/{work_id}/visualizations").status_code == 404


def test_other_outcomes_are_returned_but_not_stored(api):
    compose, clients, work_id, _ = api
    choices = store(api, "captain-1", chapter=2, query="the captain during the war")
    assert choices.status_code == 200 and choices.json()["visualization"] is None
    assert choices.json()["result"]["outcome"] == "needs_context"
    assert clients["reader"].get(f"/v1/works/{work_id}/visualizations").json()["items"] == []
    missing = clients["reader"].post(f"/v1/works/{work_id}/visualizations", json={"query": "Arthur"}, headers=ORIGIN)
    assert missing.status_code == 422


def test_stored_citations_stay_resolvable_after_new_consolidations(api, monkeypatch):
    compose, clients, work_id, story = api
    stored = store(api, "home-2", query="Arthur at home after the war").json()["visualization"]
    other = RuleAdapter(annotated_consolidation)
    other.model = "rule-v2"  # a changed model writes a new consolidation, never over the old one
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: other)
    fresh = outcome(compose(chapter=3, query="Arthur at home after the war"))["data"]
    assert fresh["lineage"]["consolidation_id"] != stored["result"]["data"]["lineage"]["consolidation_id"]
    again = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{stored['id']}").json()
    assert again == stored
    boundary = {"mode": "through_chapter", "chapter_id": str(story.chapters[3])}
    for trait in again["result"]["data"]["subject"]["traits"]:
        for span in trait["evidence"]:
            assert clients["reader"].post(f"/v1/works/{work_id}/evidence", headers=ORIGIN, json={
                "span": span, "parser_revision": again["result"]["data"]["scope"]["parser_revision"],
                "reading_boundary": boundary}).status_code == 200
