import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.appearance import AppearanceCandidate, AppearanceSubject
from app.models.entities import Entity
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.narrative_jobs import NarrativeJob
from app.models.passages import Chapter, Passage
from app.providers.deterministic import RuleAdapter, ScriptedAdapter
from app.providers.embeddings import HashedEmbeddings
from app.providers.local_entities import LocalEntities
from app.services.dispatch import dispatch_ingestions
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative import pipeline
from app.services.narrative.pipeline import execute_narrative, recover_narratives
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.test_chronology import event_rule
from tests.test_entity_extraction import fixture_rule
from tests.test_local_entities import FIXTURE_SPANS, corefer_pronouns, recognizer
from tests.test_visual_facts import fact_rule

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
STORY = Path(__file__).parent / "fixtures/narrative/story.md"
PASSWORD = "synthetic pipeline test passphrase"
RULES = {"EntityExtraction": fixture_rule, "EventExtraction": event_rule, "FactExtraction": fact_rule}


class FixtureModel:
    """Answers each extraction role with the annotated corpus rules."""
    provider, model = "deterministic", "fixture-v1"

    def __init__(self, broken: str | None = None):
        self.broken = broken

    def complete(self, call):
        title = call.output_schema["title"]
        if title == self.broken:
            return ScriptedAdapter('{"unexpected": true}').complete(call)
        return RuleAdapter(RULES[title]).complete(call)


@pytest.fixture
def clients(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    with Session(database) as db:
        db.add_all([Principal(username=n, password_hash=hash_password(PASSWORD)) for n in ("narrator", "outsider")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as owner, \
            TestClient(create_app(), base_url="http://127.0.0.1") as other:
        for client, name in [(owner, "narrator"), (other, "outsider")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": PASSWORD},
                               headers=ORIGIN).status_code == 200
        yield owner, other


def upload(client, key="pipeline-source"):
    return client.post("/v1/works", data={"title": "Pipeline", "format": "md"},
                       files={"file": ("story.md", STORY.read_bytes())},
                       headers={**ORIGIN, "Idempotency-Key": key}).json()


def generation_of(client, work_id):
    return client.get(f"/v1/works/{work_id}/generations").json()["items"][0]


def narrative_job(database, generation_id):
    with Session(database) as db:
        return db.scalar(select(NarrativeJob).where(NarrativeJob.generation_id == uuid.UUID(generation_id)))


def derivation_counts(database):
    with Session(database) as db:
        return dict(db.execute(select(Derivation.stage, func.count()).group_by(Derivation.stage)).all()), \
            db.scalar(select(func.count()).select_from(Entity))


def test_parse_queues_narrative_and_success_publishes_readiness_once(clients, database, monkeypatch):
    owner, other = clients
    accepted = upload(owner)
    work_id = accepted["work"]["id"]
    execute_ingestion(accepted["job"]["id"])
    generation = generation_of(owner, work_id)
    assert (generation["narrative_status"], generation["narrative_ready"]) == ("queued", False)
    job = narrative_job(database, generation["id"])

    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "live")
    monkeypatch.setattr(pipeline, "narrative_adapter", lambda: FixtureModel())
    execute_narrative(str(job.id))
    generation = generation_of(owner, work_id)
    assert (generation["narrative_status"], generation["narrative_ready"], generation["narrative_error"]) == (
        "succeeded", True, None)
    assert narrative_job(database, generation["id"]).stage == "narrative_ready"
    labels = {e["label"] for e in owner.get(f"/v1/works/{work_id}/entities").json()["items"]}
    assert {"Arthur", "Wren", "Mira", "Brann"} <= labels
    assert other.get(f"/v1/works/{work_id}/entities").status_code == 404

    before = derivation_counts(database)
    with database.begin() as connection:  # redelivery after success is a no-op
        connection.execute(update(NarrativeJob).values(status="queued"))
    execute_narrative(str(job.id))
    assert derivation_counts(database) == before == ({"entities": 1, "events": 1, "facts": 1}, 8)


def test_disabled_provider_and_invalid_extraction_are_never_advertised_ready(clients, database, monkeypatch):
    owner, _ = clients
    accepted = upload(owner)
    work_id = accepted["work"]["id"]
    execute_ingestion(accepted["job"]["id"])
    job = narrative_job(database, generation_of(owner, work_id)["id"])

    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "off")
    execute_narrative(str(job.id))
    generation = generation_of(owner, work_id)
    assert (generation["narrative_status"], generation["narrative_error"], generation["narrative_ready"]) == (
        "failed", "PROVIDER_NOT_ENABLED", False)
    assert owner.get(f"/v1/works/{work_id}/entities").json()["error"]["code"] == "NARRATIVE_NOT_READY"

    with database.begin() as connection:
        connection.execute(update(NarrativeJob).values(status="queued"))
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "live")
    monkeypatch.setattr(pipeline, "narrative_adapter", lambda: FixtureModel(broken="EventExtraction"))
    execute_narrative(str(job.id))
    stored = narrative_job(database, generation_of(owner, work_id)["id"])
    assert (stored.status, stored.stage, stored.error_code) == ("failed", "failed", "PROVIDER_INVALID_OUTPUT")
    assert generation_of(owner, work_id)["narrative_ready"] is False
    assert owner.get(f"/v1/works/{work_id}/entities").status_code == 200  # entities exist but not advertised ready

    with database.begin() as connection:
        connection.execute(update(NarrativeJob).values(status="queued"))
    monkeypatch.setattr(pipeline, "narrative_adapter", lambda: FixtureModel())
    execute_narrative(str(job.id))
    assert generation_of(owner, work_id)["narrative_ready"] is True
    stages, entities = derivation_counts(database)
    assert stages == {"entities": 1, "events": 1, "facts": 1} and entities == 8  # retry reused, not duplicated


def test_local_mode_publishes_entities_and_appearance_without_a_provider(clients, database, monkeypatch):
    owner, _ = clients
    accepted = upload(owner)
    work_id = accepted["work"]["id"]
    execute_ingestion(accepted["job"]["id"])
    job = narrative_job(database, generation_of(owner, work_id)["id"])
    monkeypatch.delenv("VISION_NARRATIVE_PROVIDER", raising=False)  # local is the default
    monkeypatch.delenv("VISION_LLM_API_KEY", raising=False)
    monkeypatch.setattr(pipeline, "local_adapter",
                        lambda: LocalEntities(recognizer(FIXTURE_SPANS), corefer_pronouns("Arthur")))
    monkeypatch.setattr(pipeline, "local_embedder", HashedEmbeddings)
    released = []
    monkeypatch.setattr(pipeline, "release_models", lambda: released.append(narrative_job(database, str(job.generation_id)).stage))
    execute_narrative(str(job.id))
    assert released == ["entities", "appearance", "index"]  # weights never outlive the stage that loaded them
    generation = generation_of(owner, work_id)
    assert (generation["narrative_status"], generation["narrative_ready"]) == ("succeeded", True)
    assert {"Arthur", "Wren", "Captain Mira"} <= {e["label"] for e in owner.get(f"/v1/works/{work_id}/entities").json()["items"]}
    with Session(database) as db:
        assert dict(db.execute(select(Derivation.stage, func.count()).group_by(Derivation.stage)).all()) == {
            "entities": 1, "appearance": 1, "index": 1}
        assert db.get(SourceGeneration, generation["id"]).search_ready_at is not None
        arthur = db.scalar(select(Entity.id).where(Entity.label == "Arthur"))
        described = db.scalars(select(AppearanceCandidate).join(AppearanceSubject).where(
            AppearanceSubject.entity_id == arthur)).all()
        texts = [db.get(Passage, c.passage_id).text[c.start:c.end] for c in described]
    assert any("scar" in t for t in texts) and any("chestnut hair" in t for t in texts)


def test_interrupted_jobs_are_requeued_within_their_attempt_budget(clients, database):
    owner, _ = clients
    accepted = upload(owner)
    execute_ingestion(accepted["job"]["id"])
    job = narrative_job(database, generation_of(owner, accepted["work"]["id"])["id"])
    with database.begin() as connection:
        connection.execute(update(NarrativeJob).values(status="running", attempts=1, dispatched_at=func.now()))
    assert recover_narratives(database) == 1
    assert (narrative_job(database, str(job.generation_id)).status,
            narrative_job(database, str(job.generation_id)).dispatched_at) == ("queued", None)
    with database.begin() as connection:
        connection.execute(update(NarrativeJob).values(status="running", attempts=3))
    recover_narratives(database)
    stored = narrative_job(database, str(job.generation_id))
    assert (stored.status, stored.error_code) == ("failed", "ATTEMPTS_EXHAUSTED")


class FakeGateway(BaseHTTPRequestHandler):
    """OpenAI-compatible chat endpoint answering with the fixture rules; no external network."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system, data = body["messages"][0]["content"], body["messages"][1]["content"]
        schema = json.loads(system.rsplit("JSON Schema:\n", 1)[1])
        content = json.dumps(RULES[schema["title"]](json.loads(data)["sources"]))
        payload = json.dumps({"model": "fixture/gateway", "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                              "choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def test_real_upload_worker_gateway_and_scoped_browse(clients, database, monkeypatch, tmp_path):
    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Set VISION_TEST_REDIS_URL for the real worker pipeline")
    server = HTTPServer(("127.0.0.1", 0), FakeGateway)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "live")
    monkeypatch.setenv("VISION_LLM_API_KEY", "freellmapi-synthetic")
    monkeypatch.setenv("VISION_LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    owner, other = clients
    api = Path(__file__).parents[1]
    with (tmp_path / "pipeline-worker.log").open("w") as log:
        worker = subprocess.Popen([str(api / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1",
                                   "--threads", "1"], cwd=api, env=os.environ.copy(), stdout=log, stderr=log)
        try:
            accepted = upload(owner, "pipeline-worker-source")
            work_id = accepted["work"]["id"]
            dispatch_ingestions(database)
            for _ in range(600):
                generation = generation_of(owner, work_id)
                if generation["narrative_status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.1)
            assert (generation["narrative_status"], generation["narrative_ready"]) == ("succeeded", True), \
                (tmp_path / "pipeline-worker.log").read_text()[-2000:]
        finally:
            worker.terminate()
            worker.wait(timeout=15)
            server.shutdown()
    chapters = owner.get(f"/v1/works/{work_id}/entities").json()
    arthur = next(e for e in chapters["items"] if e["label"] == "Arthur")
    assert "Wren" in {a["label"] for a in arthur["aliases"]}
    with Session(database) as db:
        two = db.scalar(select(Chapter.id).where(Chapter.document_id == uuid.UUID(accepted["work"]["document_id"]),
                                                 Chapter.ordinal == 2))
    early = owner.get(f"/v1/works/{work_id}/entities/{arthur['id']}", params={"through_chapter_id": str(two)}).json()
    assert early["relations"] == [] and "Élodie remembers Arthur at ten" not in {e["label"] for e in early["events"]}
    assert other.get(f"/v1/works/{work_id}/entities/{arthur['id']}").status_code == 404
    with Session(database) as db:
        assert set(db.scalars(select(Derivation.status))) == {"succeeded"}


@pytest.mark.skipif(os.environ.get("VISION_LOCAL_MODELS") != "1",
                    reason="Set VISION_LOCAL_MODELS=1 to run the pinned local models in a real worker")
def test_real_worker_runs_local_models_without_network(clients, database, monkeypatch, tmp_path):
    redis_url = os.environ.get("VISION_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Set VISION_TEST_REDIS_URL for the real worker pipeline")
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")  # models must already be cached; nothing is fetched
    monkeypatch.delenv("VISION_LLM_API_KEY", raising=False)
    owner, _ = clients
    api = Path(__file__).parents[1]
    with (tmp_path / "local-worker.log").open("w") as log:
        worker = subprocess.Popen([str(api / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1",
                                   "--threads", "1"], cwd=api, env=os.environ.copy(), stdout=log, stderr=log)
        try:
            accepted = upload(owner, "local-worker-source")
            work_id = accepted["work"]["id"]
            dispatch_ingestions(database)
            for _ in range(1800):
                generation = generation_of(owner, work_id)
                if generation["narrative_status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.1)
            assert (generation["narrative_status"], generation["narrative_ready"]) == ("succeeded", True), \
                (tmp_path / "local-worker.log").read_text()[-2000:]
        finally:
            worker.terminate()
            worker.wait(timeout=15)
    arthur = next(e for e in owner.get(f"/v1/works/{work_id}/entities").json()["items"] if e["label"] == "Arthur")
    assert "Wren" in {a["label"] for a in arthur["aliases"]}
    with Session(database) as db:
        assert dict(db.execute(select(Derivation.stage, Derivation.status)).all()) == {
            "entities": "succeeded", "appearance": "succeeded", "index": "succeeded"}
