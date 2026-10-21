import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.entities import (
    Entity,
    EntityAlias,
    EntityMention,
    EntityRelation,
    MentionCandidate,
)
from app.models.model_runs import Derivation, ModelRun
from app.models.passages import Passage
from app.providers.contracts import (
    Limits,
    ProviderCall,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.providers.deterministic import RuleAdapter, ScriptedAdapter
from app.providers.extraction import KNOWN_REF
from app.providers.openai_compatible import ChatGateway, strip_fence
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.derivations import batches
from app.services.narrative.entities import derive_entities
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.narrative_eval import evaluate, mention_rows

ORIGIN = {"Origin": "http://127.0.0.1:3000"}
STORY = Path(__file__).parent / "fixtures/narrative/story.md"
REVEAL = "Only this chapter established that Wren and Arthur were the same person."
ENTITIES = {"arthur": ("character", "Arthur"), "elodie": ("character", "Élodie"), "mira": ("character", "Mira"),
            "brann": ("character", "Brann"), "wren": ("character", "Wren"),
            "house": ("place", "house by the ash tree"), "compass": ("object", "brass compass"),
            "sword": ("object", "silver sword"), "ghost": ("character", "Ghost")}
MENTIONS = [("Arthur", "arthur", []), ("Élodie", "elodie", []), ("Mira", "mira", []), ("Brann", "brann", []),
            ("Wren", "wren", []), ("house by the ash tree", "house", []), ("brass compass", "compass", []),
            ("silver sword", "sword", []), ("house's", "house", []), ("captain", None, ["mira", "brann"]),
            # Hostile model items: an invented quote and an undeclared identity.
            ("Arthur had wings of fire", "arthur", []), ("masked visitor", "ghost-missing", [])]
ALIASES = [("mira", "Captain Mira", "supported", "Captain Mira carried a brass compass."),
           ("brann", "Captain Brann", "supported", "Captain Brann carried a silver sword."),
           ("mira", "captain", "candidate", "Mira and Brann were both called captain"),
           ("brann", "captain", "candidate", "Mira and Brann were both called captain"),
           ("arthur", "Wren", "supported", REVEAL),
           ("arthur", "Iron Wolf", "supported", "A poet called Arthur a wolf made of iron.")]
RELATIONS = [("mira", "carries", "compass", "Captain Mira carried a brass compass."),
             ("brann", "carries", "sword", "Captain Brann carried a silver sword."),
             ("wren", "same_as", "arthur", REVEAL)]


def fixture_rule(sources):
    """An 'ideal model' over whatever passages a batch holds, plus deliberately bad items."""
    text = [s for s in sources if s["ref"] != KNOWN_REF]  # derived listing, never source text

    def found(quote):
        return next((s["ref"] for s in text if quote in s["text"]), None)

    mentions = []
    for quote, entity, candidates in MENTIONS:
        ref = found("dreamed") if quote.startswith("Arthur had") else found(quote)
        if ref:
            mentions.append({"ref": ref, "quote": quote, "entity": entity, "candidates": candidates})
    used = {k for m in mentions for k in [m["entity"], *m["candidates"]] if k in ENTITIES}
    return {
        "entities": [{"key": k, "kind": ENTITIES[k][0], "label": ENTITIES[k][1]} for k in sorted(used)],
        "mentions": mentions,
        "aliases": [{"entity": e, "label": label, "status": status, "ref": found(q), "quote": q}
                    for e, label, status, q in ALIASES if found(q) and e in used],
        "relations": [{"subject": s, "relation": r, "object": o, "ref": found(q), "quote": q}
                      for s, r, o, q in RELATIONS if found(q) and {s, o} <= used],
    }


def fixture_adapter(model="rule-v1"):
    adapter = RuleAdapter(fixture_rule)
    adapter.model = model
    return adapter


@pytest.fixture
def generation(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    password = "synthetic entity test passphrase"
    with Session(database) as db:
        db.add(Principal(username="entity_owner", password_hash=hash_password(password)))
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "entity_owner", "password": password},
                           headers=ORIGIN).status_code == 200
        accepted = client.post("/v1/works", data={"title": "Entities", "format": "md"},
                               files={"file": ("story.md", STORY.read_bytes())},
                               headers={**ORIGIN, "Idempotency-Key": "entity-source"}).json()
        execute_ingestion(accepted["job"]["id"])
        items = client.get(f"/v1/works/{accepted['work']['id']}/generations").json()["items"]
    return items[0]["id"]


def counts(db, derivation_id):
    return {model.__name__: db.scalar(select(func.count()).select_from(model).where(model.derivation_id == derivation_id))
            for model in (Entity, EntityMention, EntityRelation, ModelRun)}


@pytest.mark.integration
def test_fixture_derivation_keeps_ambiguity_spans_and_lineage(database, generation):
    derivation_id = derive_entities(database, generation, fixture_adapter())
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        assert (derivation.status, derivation.attempt) == ("succeeded", 1)
        assert derivation.processing_version == "entities-v2/entities-schema-v3/deterministic/rule-v1"
        assert derivation.rejections == {"ungrounded": 2, "unknown_entity": 1}
        report = evaluate(db, derivation_id)
        assert report == {"misses": [], "false_merges": [], "splits": [], "unmatched_entities": [],
                          "ambiguity_violations": []}
        labels = {e.id: e.label for e in db.scalars(select(Entity).where(Entity.derivation_id == derivation_id))}
        assert sorted(labels.values()) == sorted(v[1] for k, v in ENTITIES.items() if k != "ghost")
        rows = mention_rows(db, derivation_id)
        runs = {r.id for r in db.scalars(select(ModelRun).where(ModelRun.derivation_id == derivation_id))}
        for mention, passage, text, candidates in rows:
            assert passage.text[mention.start:mention.end] == text and mention.model_run_id in runs
        captain = [(m, c) for m, p, text, c in rows if text == "captain"]
        assert len(captain) == 1 and captain[0][0].entity_id is None
        assert {labels[i] for i in captain[0][1]} == {"Mira", "Brann"}
        early_wren = [m for m, p, text, c in rows if text == "Wren" and p.chapter_ordinal < 5]
        assert early_wren and all(labels[m.entity_id] == "Wren" for m in early_wren)
        relations = db.execute(select(EntityRelation, Passage).join(Passage, Passage.id == EntityRelation.passage_id)
                               .where(EntityRelation.derivation_id == derivation_id)).all()
        same = [(r, p) for r, p in relations if r.relation == "same_as"]
        assert len(same) == 1 and same[0][1].chapter_ordinal == 5
        assert (labels[same[0][0].subject_id], labels[same[0][0].object_id]) == ("Wren", "Arthur")
        aliases = db.execute(select(EntityAlias.label, EntityAlias.status, Entity.label)
                             .join(Entity, Entity.id == EntityAlias.entity_id)
                             .where(Entity.derivation_id == derivation_id)).all()
        assert sorted(aliases) == sorted([("Captain Mira", "supported", "Mira"), ("Captain Brann", "supported", "Brann"),
                                          ("captain", "candidate", "Mira"), ("captain", "candidate", "Brann"),
                                          ("Wren", "supported", "Arthur")])
        assert len(runs) == 5  # one chapter-aligned call per chapter


@pytest.mark.integration
def test_rerun_is_idempotent_and_a_changed_model_adds_a_derivation(database, generation):
    first = derive_entities(database, generation, fixture_adapter())
    with Session(database) as db:
        before = counts(db, first)
        ids = set(db.scalars(select(Entity.id).where(Entity.derivation_id == first)))
    assert derive_entities(database, generation, fixture_adapter()) == first
    second = derive_entities(database, generation, fixture_adapter("rule-v2"))
    assert second != first
    with Session(database) as db:
        assert counts(db, first) == before
        assert set(db.scalars(select(Entity.id).where(Entity.derivation_id == first))) == ids
        assert db.get(Derivation, second).status == "succeeded"
        assert db.scalar(select(func.count()).select_from(Derivation)) == 2


@pytest.mark.integration
def test_failed_or_invalid_extraction_writes_no_entities_and_retry_publishes(database, generation):
    good = fixture_adapter()
    calls = []

    def flaky(sources):  # the second batch is down for all of its bounded retries
        calls.append(1)
        if len(calls) >= 2:
            raise ProviderUnavailable()
        return fixture_rule(sources)

    failed = derive_entities(database, generation, RuleAdapter(flaky))
    with Session(database) as db:
        derivation = db.get(Derivation, failed)
        assert (derivation.status, derivation.error_code) == ("failed", "PROVIDER_UNAVAILABLE")
        assert counts(db, failed) == {"Entity": 0, "EntityMention": 0, "EntityRelation": 0, "ModelRun": 4}
    assert derive_entities(database, generation, good) == failed
    with Session(database) as db:
        derivation = db.get(Derivation, failed)
        assert (derivation.status, derivation.attempt, derivation.error_code) == ("succeeded", 2, None)
        assert counts(db, failed)["Entity"] == 8

    invalid = ScriptedAdapter(*['{"entities": [], "mentions": [], "unexpected": 1}'] * 3)
    invalid.model = "scripted-invalid"
    bad = derive_entities(database, generation, invalid)
    with Session(database) as db:
        derivation = db.get(Derivation, bad)
        assert (derivation.status, derivation.error_code) == ("failed", "PROVIDER_INVALID_OUTPUT")
        assert counts(db, bad) == {"Entity": 0, "EntityMention": 0, "EntityRelation": 0, "ModelRun": 3}

    class Recovering:  # first call is malformed, the bounded retry succeeds
        provider, model, calls = "deterministic", "rule-recovers", 0

        def complete(self, call):
            self.calls += 1
            return ScriptedAdapter("not json").complete(call) if self.calls == 1 else fixture_adapter().complete(call)

    healed = derive_entities(database, generation, Recovering())
    with Session(database) as db:
        assert db.get(Derivation, healed).status == "succeeded"
        assert [r.outcome for r in db.scalars(select(ModelRun).where(ModelRun.derivation_id == healed)
                                              .order_by(ModelRun.started_at))][:2] == ["invalid_output", "succeeded"]


@pytest.mark.integration
def test_superseded_or_cancelled_attempt_cannot_publish(database, generation):
    adapter = fixture_adapter()

    def superseded():
        with database.begin() as connection:
            connection.execute(update(Derivation).values(attempt=Derivation.attempt + 1))
        return False

    stale = derive_entities(database, generation, adapter, cancelled=superseded)
    with Session(database) as db:
        assert counts(db, stale) == {"Entity": 0, "EntityMention": 0, "EntityRelation": 0, "ModelRun": 0}
        assert db.get(Derivation, stale).status == "running"

    cancelled = derive_entities(database, generation, adapter, cancelled=lambda: True)
    with Session(database) as db:
        derivation = db.get(Derivation, cancelled)
        assert (derivation.status, derivation.error_code) == ("cancelled", None)
        assert counts(db, cancelled)["Entity"] == 0 and db.scalar(
            select(func.count()).select_from(MentionCandidate)) == 0


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("VISION_LIVE_PROVIDER") != "1" or not os.environ.get("VISION_LLM_API_KEY"),
                    reason="Set VISION_LIVE_PROVIDER=1 and VISION_LLM_API_KEY to send the synthetic corpus to the gateway")
def test_live_gateway_extraction_on_the_synthetic_fixture(database, generation):
    adapter = ChatGateway.from_environment()
    derivation_id = derive_entities(database, generation, adapter, Limits(timeout_seconds=120, max_output_tokens=4_096))
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        runs = db.scalars(select(ModelRun).where(ModelRun.derivation_id == derivation_id)).all()
        report = evaluate(db, derivation_id) if derivation.status == "succeeded" else None
        for mention, passage, text, _ in mention_rows(db, derivation_id):
            assert passage.text[mention.start:mention.end] == text
    print(json.dumps({"status": derivation.status, "error_code": derivation.error_code,
                      "rejections": derivation.rejections, "report": report,
                      "runs": [(r.outcome, r.model_version, r.input_tokens, r.output_tokens, r.duration_ms) for r in runs]},
                     ensure_ascii=False, indent=1))
    assert derivation.status in {"succeeded", "failed"} and runs


def test_batches_follow_chapters_and_input_bounds():
    passage = lambda ordinal, chapter, size: SimpleNamespace(ordinal=ordinal, chapter_ordinal=chapter, text="x" * size)  # noqa: E731
    passages = [passage(0, 1, 100), passage(1, 1, 100), passage(2, 2, 100), passage(3, 2, 30_000), passage(4, 2, 30_000)]
    groups = batches(passages, 40_000)
    assert [[p.ordinal for p in group] for group in groups] == [[0, 1], [2, 3], [4]]
    assert batches([], 1_000) == []


class Gateway(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.headers["Authorization"], body))
        status, payload = self.server.replies.pop(0)
        if status == "hang":
            threading.Event().wait(2)
            status = 200
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def gateway():
    server = HTTPServer(("127.0.0.1", 0), Gateway)
    server.seen, server.replies = [], []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def chat_call(timeout=5):
    return ProviderCall(system="sys", data='{"sources": []}', output_schema={"type": "object"},
                        max_output_tokens=64, timeout_seconds=timeout)


def test_chat_gateway_sends_bounded_json_request_and_maps_failures(gateway):
    adapter = ChatGateway(f"http://127.0.0.1:{gateway.server_port}/v1", "freellmapi-synthetic", "auto")
    gateway.replies = [(200, {"model": "routed/model-x", "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                              "choices": [{"message": {"content": '```json\n{"names": []}\n```'}}]}),
                       (401, {"error": {"message": "Invalid API key"}}), (503, {}), (200, {"choices": []}),
                       ("hang", {})]
    result = adapter.complete(chat_call())
    assert (result.output, result.model_version, result.usage.input_tokens) == ('{"names": []}', "routed/model-x", 12)
    authorization, body = gateway.seen[0]
    assert authorization == "Bearer freellmapi-synthetic"
    assert (body["model"], body["max_tokens"], body["temperature"], body["response_format"]) == (
        "auto", 64, 0, {"type": "json_object"})
    assert [m["role"] for m in body["messages"]] == ["system", "user"] and body["messages"][1]["content"] == '{"sources": []}'
    assert "tools" not in body
    for _ in range(3):
        with pytest.raises(ProviderUnavailable):
            adapter.complete(chat_call())
    with pytest.raises(ProviderTimeout):
        adapter.complete(chat_call(timeout=0.5))
    with pytest.raises(ProviderUnavailable):
        ChatGateway("http://127.0.0.1:9/v1", "k", "auto").complete(chat_call())


def test_gateway_is_disabled_without_a_key_and_fences_are_stripped(monkeypatch):
    monkeypatch.delenv("VISION_LLM_API_KEY", raising=False)
    assert ChatGateway.from_environment() is None
    monkeypatch.setenv("VISION_LLM_API_KEY", "freellmapi-synthetic")
    monkeypatch.setenv("VISION_LLM_MODEL", "auto:smart")
    adapter = ChatGateway.from_environment()
    assert (adapter.provider, adapter.model, adapter.base_url) == ("freellm", "auto:smart", "http://127.0.0.1:3001/v1")
    assert strip_fence('```\n{"a": 1}\n```') == '{"a": 1}' and strip_fence(' {"a": 1} ') == '{"a": 1}'
