from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.entities import Entity
from app.models.events import Event
from app.models.passages import Chapter
from app.models.visual_facts import FactEvent, VisualFact
from app.providers.deterministic import RuleAdapter
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.entities import derive_entities
from app.services.narrative.events import derive_events
from app.services.narrative.visual_facts import derive_visual_facts
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from tests.test_chronology import event_rule
from tests.test_entity_extraction import fixture_adapter
from tests.test_visual_facts import fact_rule

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
STORY = Path(__file__).parent / "fixtures/narrative/story.md"


@pytest.fixture
def narrative(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    password = "synthetic eligibility test passphrase"
    with Session(database) as db:
        db.add_all([Principal(username=n, password_hash=hash_password(password)) for n in ("reader", "stranger")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as reader, \
            TestClient(create_app(), base_url="http://127.0.0.1") as stranger:
        for client, name in [(reader, "reader"), (stranger, "stranger")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": password},
                               headers=ORIGIN).status_code == 200
        work = reader.post("/v1/works", data={"title": "Eligibility", "format": "md"},
                           files={"file": ("story.md", STORY.read_bytes())},
                           headers={**ORIGIN, "Idempotency-Key": "eligibility-source"}).json()
        execute_ingestion(work["job"]["id"])
        generation = reader.get(f"/v1/works/{work['work']['id']}/generations").json()["items"][0]["id"]
        not_ready = reader.get(f"/v1/works/{work['work']['id']}/entities")
        assert (not_ready.status_code, not_ready.json()["error"]["code"]) == (409, "NARRATIVE_NOT_READY")
        entities = derive_entities(database, generation, fixture_adapter())
        events = derive_events(database, generation, entities, RuleAdapter(event_rule))
        derive_visual_facts(database, generation, events, RuleAdapter(fact_rule))
        with Session(database) as db:
            chapters = {c.ordinal: str(c.id) for c in db.scalars(select(Chapter).where(
                Chapter.document_id == work["work"]["document_id"]))}
        yield reader, stranger, work["work"]["id"], chapters


def browse(client, work_id, chapter=None, entity=None):
    path = f"/v1/works/{work_id}/entities" + (f"/{entity}" if entity else "")
    response = client.get(path, params={"through_chapter_id": chapter} if chapter else None)
    assert response.status_code == 200, response.text
    return response.json()


def by_label(page):
    return {item["label"]: item for item in page["items"]}


def test_identity_revealed_late_stays_separate_before_the_revelation(narrative):
    reader, _, work_id, chapters = narrative
    whole = by_label(browse(reader, work_id))
    assert ("Wren", "supported") in {(a["label"], a["status"]) for a in whole["Arthur"]["aliases"]}
    detail = browse(reader, work_id, entity=whole["Arthur"]["id"])
    assert [r["relation"] for r in detail["relations"]] == ["same_as"]
    assert detail["relations"][0]["span"]["quote"] == "Only this chapter established that Wren and Arthur were the same person."

    for ordinal in (1, 2, 3, 4):
        early = by_label(browse(reader, work_id, chapters[ordinal]))
        assert {"Arthur", "Wren"} <= early.keys()
        assert "Wren" not in {a["label"] for a in early["Arthur"]["aliases"]}
        assert browse(reader, work_id, chapters[ordinal], early["Arthur"]["id"])["relations"] == []
    captain = [m for m in browse(reader, work_id, chapters[2], whole["Mira"]["id"])["mentions"]
               if m["span"]["quote"] == "captain"]
    assert captain[0]["entity_id"] is None and set(captain[0]["candidate_ids"]) == {whole["Mira"]["id"], whole["Brann"]["id"]}


def test_later_events_facts_and_conflicts_are_hidden_even_when_story_early(narrative):
    reader, _, work_id, chapters = narrative
    arthur = by_label(browse(reader, work_id))["Arthur"]["id"]
    whole = browse(reader, work_id, entity=arthur)
    assert "Élodie remembers Arthur at ten" in {e["label"] for e in whole["events"]}
    assert len(whole["conflicts"]) == 1

    two = browse(reader, work_id, chapters[2], arthur)
    labels = {e["label"] for e in two["events"]}
    assert "Arthur at ten" in labels and "the war" in labels
    assert "Élodie remembers Arthur at ten" not in labels  # childhood memory told in chapter five
    values = {(f["attribute"], f["value"]) for f in two["facts"]}
    assert ("left_cheek", "scar") in values and ("left_cheek", "scar still visible") not in values
    assert not any(f["perspective"] == "Élodie" for f in two["facts"])
    visible_events = {e["id"] for e in two["events"]}
    assert {r["relation"] for r in two["event_relations"]} == {"before", "during"}
    assert all({r["source_id"], r["target_id"]} <= visible_events for r in two["event_relations"])

    three, four = browse(reader, work_id, chapters[3], arthur), browse(reader, work_id, chapters[4], arthur)
    assert three["conflicts"] == [] and not {f["value"] for f in three["facts"]} & {"green", "blue"}
    assert len(four["conflicts"]) == 1 and {"green", "blue"} <= {f["value"] for f in four["facts"]}


def test_derived_dependencies_and_labels_cannot_leak_past_the_cutoff(narrative, database):
    reader, _, work_id, chapters = narrative
    with Session(database) as db:
        wren = db.scalar(select(Entity).where(Entity.label == "Wren"))
        wren.label = "Arthur in disguise"
        chestnut = db.scalar(select(VisualFact).where(VisualFact.value == "chestnut"))
        memory = db.scalar(select(Event).where(Event.label == "Élodie remembers Arthur at ten"))
        db.add(FactEvent(fact_id=chestnut.id, event_id=memory.id))
        db.commit()
    early = by_label(browse(reader, work_id, chapters[1]))
    assert "Wren" in early and "Arthur in disguise" not in early
    arthur = early["Arthur"]["id"]
    assert ("hair", "chestnut") not in {(f["attribute"], f["value"]) for f in browse(reader, work_id, chapters[1], arthur)["facts"]}
    assert ("hair", "chestnut") in {(f["attribute"], f["value"]) for f in browse(reader, work_id, None, arthur)["facts"]}
    with database.begin() as connection:
        connection.execute(update(Entity).where(Entity.label == "Arthur in disguise").values(label="Wren"))


def test_owner_chapter_and_hidden_entity_requests_fail_safely(narrative):
    reader, stranger, work_id, chapters = narrative
    arthur = by_label(browse(reader, work_id))["Arthur"]["id"]
    for client, path, params in [
        (stranger, f"/v1/works/{work_id}/entities", None),
        (stranger, f"/v1/works/{work_id}/entities/{arthur}", None),
        (reader, f"/v1/works/{work_id}/entities", {"through_chapter_id": "00000000-0000-0000-0000-000000000000"}),
        (reader, f"/v1/works/{work_id}/entities/00000000-0000-0000-0000-000000000000", None),
    ]:
        response = client.get(path, params=params)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "RESOURCE_NOT_FOUND")
    spans = browse(reader, work_id, chapters[1], arthur)["mentions"]
    evidence = reader.post(f"/v1/works/{work_id}/evidence", headers=ORIGIN, json={
        "span": {k: v for k, v in spans[0]["span"].items() if k != "offset_unit"},
        "parser_revision": browse(reader, work_id)["scope"]["parser_revision"],
        "reading_boundary": {"mode": "through_chapter", "chapter_id": chapters[1]}})
    assert evidence.status_code == 200 and evidence.json()["span"]["quote"] == "Arthur"
