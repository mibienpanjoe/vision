"""The real compose endpoint over stored source evidence, with deterministic consolidation and adjudication."""

import pytest
from app.main import create_app
from app.providers.contracts import ProviderRateLimited
from app.providers.deterministic import RuleAdapter
from app.providers.embeddings import HashedEmbeddings
from app.schemas.visualization import VisualizationResult
from app.services.narrative import pipeline
from app.services.retrieval.semantic import index_passages
from app.services.visualization import specification
from fastapi.testclient import TestClient
from tests.conftest import ORIGIN
from tests.test_appearance_states import annotated_consolidation
from tests.test_grounding_verification import verdict_rule

pytestmark = pytest.mark.integration
PASSWORD = "synthetic query plan passphrase"


@pytest.fixture
def api(story, monkeypatch):
    index_passages(story.engine, story.generation, HashedEmbeddings())
    monkeypatch.setattr(pipeline, "local_embedder", HashedEmbeddings)
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: RuleAdapter(annotated_consolidation))
    monkeypatch.setattr(specification, "adjudicator", lambda _: RuleAdapter(verdict_rule({
        "plain linen shirt": ("entailed", None)})))
    clients = {}
    with TestClient(create_app(), base_url="http://127.0.0.1") as reader, \
            TestClient(create_app(), base_url="http://127.0.0.1") as stranger:
        for client, name in [(reader, "reader"), (stranger, "stranger")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": PASSWORD},
                               headers=ORIGIN).status_code == 200
            clients[name] = client
        work_id = str(story.plan(None, query="Arthur").work_id)

        def compose(client="reader", chapter=None, **body):
            if chapter is not None:
                body["through_chapter_id"] = str(story.chapters[chapter])
            return clients[client].post(f"/v1/works/{work_id}/visualizations/compose", json=body, headers=ORIGIN)
        yield compose, clients, work_id, story


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
