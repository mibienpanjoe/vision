"""Explicitly opted-in PostgreSQL tests, isolated from the reader's database."""

import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from app.core.passwords import hash_password
from app.core.security import ActorScope
from app.main import create_app
from app.models.access import Principal
from app.models.entities import Entity
from app.models.passages import Chapter
from app.schemas.retrieval import VisualizationRequest
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.appearance import derive_appearance
from app.services.narrative.entities import derive_entities
from app.services.retrieval.query_plan import plan_query
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("VISION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set VISION_TEST_ADMIN_URL to opt into isolated PostgreSQL tests")
    name = "vision_test_" + uuid.uuid4().hex
    admin = create_engine(
        make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = make_url(url).set(database=name)
    monkeypatch.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
    # Workers started by tests skip narrative jobs unless a test opts into a mode; local models are heavy.
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "off")
    engine = create_engine(test_url)
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


ORIGIN = {"Origin": "http://127.0.0.1:3000"}
STORY = Path(__file__).parent / "fixtures/narrative/story.md"


@pytest.fixture
def story(database, monkeypatch, tmp_path):
    """The synthetic corpus parsed, with fixture entities and appearance cues, plus a second work."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    password = "synthetic query plan passphrase"
    with Session(database) as db:
        db.add_all([Principal(username=n, password_hash=hash_password(password)) for n in ("reader", "stranger")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "reader", "password": password},
                           headers=ORIGIN).status_code == 200
        accepted = client.post("/v1/works", data={"title": "Plans", "format": "md"},
                               files={"file": ("story.md", STORY.read_bytes())},
                               headers={**ORIGIN, "Idempotency-Key": "plan-source"}).json()
        other = client.post("/v1/works", data={"title": "Same text, other work", "format": "md"},
                            files={"file": ("story.md", STORY.read_bytes())},
                            headers={**ORIGIN, "Idempotency-Key": "plan-other"}).json()
        execute_ingestion(accepted["job"]["id"])
        execute_ingestion(other["job"]["id"])
        work_id = uuid.UUID(accepted["work"]["id"])
        generation = client.get(f"/v1/works/{work_id}/generations").json()["items"][0]["id"]
    from tests.test_entity_extraction import fixture_adapter

    entities = derive_entities(database, generation, fixture_adapter())
    derive_appearance(database, uuid.UUID(generation), entities)
    with Session(database) as db:
        actors = {p.username: ActorScope(p.id, p.username) for p in db.scalars(select(Principal))}
        chapters = {c.ordinal: c.id for c in db.scalars(select(Chapter).where(
            Chapter.document_id == uuid.UUID(accepted["work"]["document_id"])))}
        ids = {e.label: e.id for e in db.scalars(select(Entity))}

        def plan(through=None, actor="reader", **fields):
            if through is not None:
                fields["through_chapter_id"] = str(chapters[through])
            return plan_query(db, actors[actor], work_id, visualization_request(**fields))
        yield SimpleNamespace(plan=plan, ids=ids, chapters=chapters, db=db, engine=database,
                              generation=uuid.UUID(generation), other_document=uuid.UUID(other["work"]["document_id"]))


def visualization_request(**fields) -> VisualizationRequest:
    return VisualizationRequest.model_validate_json(json.dumps(fields))


@pytest.fixture
def api(story, monkeypatch):
    """`story` behind the real HTTP API, with deterministic consolidation, adjudication and embeddings."""
    from app.providers.deterministic import RuleAdapter
    from app.providers.embeddings import HashedEmbeddings
    from app.services.narrative import pipeline
    from app.services.retrieval.semantic import index_passages
    from app.services.visualization import specification
    from tests.test_appearance_states import annotated_consolidation
    from tests.test_grounding_verification import verdict_rule

    index_passages(story.engine, story.generation, HashedEmbeddings())
    monkeypatch.setattr(pipeline, "local_embedder", HashedEmbeddings)
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: RuleAdapter(annotated_consolidation))
    monkeypatch.setattr(specification, "adjudicator", lambda _: RuleAdapter(verdict_rule({
        "plain linen shirt": ("entailed", None)})))
    clients = {}
    with TestClient(create_app(), base_url="http://127.0.0.1") as reader, \
            TestClient(create_app(), base_url="http://127.0.0.1") as stranger:
        for client, name in [(reader, "reader"), (stranger, "stranger")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": "synthetic query plan passphrase"},
                               headers=ORIGIN).status_code == 200
            clients[name] = client
        work_id = str(story.plan(None, query="Arthur").work_id)

        def compose(client="reader", chapter=None, **body):
            if chapter is not None:
                body["through_chapter_id"] = str(story.chapters[chapter])
            return clients[client].post(f"/v1/works/{work_id}/visualizations/compose", json=body, headers=ORIGIN)
        yield compose, clients, work_id, story


@pytest.fixture
def renders(monkeypatch, tmp_path):
    """A private render store per test."""
    monkeypatch.setenv("VISION_RENDER_ROOT", str(tmp_path / "renders"))
    return tmp_path / "renders"
