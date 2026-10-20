from pathlib import Path

import pytest
from app.core.errors import PublicError
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.passages import Passage
from app.services.ingestion import adapters, parse
from app.services.ingestion.parse import execute_ingestion
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
STORY = Path(__file__).parent / "fixtures/narrative/story.md"


@pytest.fixture
def library(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    password = "synthetic generation test passphrase"
    with Session(database) as db:
        db.add_all([Principal(username=name, password_hash=hash_password(password)) for name in ("gen_owner", "gen_other")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as owner, TestClient(create_app(), base_url="http://127.0.0.1") as other:
        for client, name in [(owner, "gen_owner"), (other, "gen_other")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": password}, headers=ORIGIN).status_code == 200
        accepted = owner.post("/v1/works", data={"title": "Generations", "format": "md"},
                              files={"file": ("story.md", STORY.read_bytes())},
                              headers={**ORIGIN, "Idempotency-Key": "generation-source"}).json()
        execute_ingestion(accepted["job"]["id"])
        yield owner, other, accepted["work"]


def generations(client, work):
    response = client.get(f"/v1/works/{work['id']}/generations")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def rebuild(client, work, key):
    return client.post(f"/v1/works/{work['id']}/generations", headers={**ORIGIN, "Idempotency-Key": key})


def cite(client, work, database, revision, quote="I was Wren at ten."):
    with Session(database) as db:
        passage = db.scalar(select(Passage).where(Passage.document_id == work["document_id"],
                                                  Passage.parser_revision == revision, Passage.text.contains(quote)))
    if passage is None:
        return None
    start = passage.text.index(quote)
    request = {"span": {"document_revision_id": work["document_id"], "passage_id": str(passage.id),
                        "start": start, "end": start + len(quote), "quote": quote},
               "parser_revision": revision, "reading_boundary": {"mode": "whole_book"}}
    return client.post(f"/v1/works/{work['id']}/evidence", json=request, headers=ORIGIN).status_code


def summary(items):
    return [(g["ordinal"], g["parser_revision"], g["status"], g["current"]) for g in items]


def test_upload_creates_a_current_parsed_generation_without_narrative_readiness(library):
    owner, other, work = library
    [first] = generations(owner, work)
    assert summary([first]) == [(1, "text-v1", "available", True)]
    assert (first["parsed"], first["narrative_ready"], first["search_ready"]) == (True, False, False)
    assert owner.get(f"/v1/works/{work['id']}").json()["current_parser_revision"] == "text-v1"
    assert other.get(f"/v1/works/{work['id']}/generations").status_code == 404
    assert rebuild(other, work, "steal").status_code == 404
    current = rebuild(owner, work, "same-revision")
    assert (current.status_code, current.json()["error"]["code"]) == (409, "GENERATION_CURRENT")


def test_failed_rebuild_keeps_previous_generation_and_citations(library, database, monkeypatch):
    owner, _, work = library
    monkeypatch.setitem(adapters.REVISIONS, "md", "text-v2")
    accepted = rebuild(owner, work, "rebuild-v2")
    assert accepted.status_code == 202, accepted.text
    assert rebuild(owner, work, "rebuild-v2").json() == accepted.json()
    assert rebuild(owner, work, "another-key").json()["error"]["code"] == "GENERATION_IN_PROGRESS"
    building = accepted.json()
    assert (building["ordinal"], building["status"], building["current"]) == (2, "building", False)

    working = parse.parse_source

    def broken(data, source_format, revision):
        raise PublicError(422, "PARSER_FAILURE", "Injected parser failure.")
    monkeypatch.setattr(parse, "parse_source", broken)
    execute_ingestion(building["job_id"])
    assert summary(generations(owner, work)) == [(1, "text-v1", "available", True), (2, "text-v2", "failed", False)]
    assert owner.get(f"/v1/works/{work['id']}").json()["current_parser_revision"] == "text-v1"
    assert cite(owner, work, database, "text-v1") == 200
    assert cite(owner, work, database, "text-v2") is None

    monkeypatch.setattr(parse, "parse_source", working)
    job = owner.get(f"/v1/works/{work['id']}/ingestions/{building['job_id']}")
    retried = owner.post(f"/v1/works/{work['id']}/ingestions/{building['job_id']}/retry",
                         headers={**ORIGIN, "If-Match": job.headers["etag"], "Idempotency-Key": "retry-v2"})
    assert retried.status_code == 200, retried.text
    execute_ingestion(building["job_id"])
    assert summary(generations(owner, work)) == [(1, "text-v1", "available", False), (2, "text-v2", "available", True)]
    assert owner.get(f"/v1/works/{work['id']}").json()["current_parser_revision"] == "text-v2"
    # Old citations keep resolving against their original parser revision.
    assert cite(owner, work, database, "text-v1") == 200
    assert cite(owner, work, database, "text-v2") == 200


def test_publication_pointer_only_moves_forward(library, database, monkeypatch):
    from app.models.generations import SourceGeneration
    from app.models.works import Document, IngestionJob

    owner, _, work = library
    monkeypatch.setitem(adapters.REVISIONS, "md", "text-v5")
    pending = rebuild(owner, work, "rebuild-v5").json()
    monkeypatch.setitem(adapters.REVISIONS, "md", "text-v6")
    assert rebuild(owner, work, "rebuild-v6").json()["error"]["code"] == "GENERATION_IN_PROGRESS"
    monkeypatch.setitem(adapters.REVISIONS, "md", "text-v5")
    # Simulate a newer generation published concurrently by another worker.
    with Session(database) as db:
        document = db.get(Document, work["document_id"])
        newer = SourceGeneration(document_id=document.id, ordinal=99, parser_revision="text-v99",
                                 idempotency_key="concurrent")
        db.add(newer)
        db.flush()
        db.add(IngestionJob(document_id=document.id, generation_id=newer.id, processing_version="text-v99",
                            status="succeeded", stage="parsed", correlation_id="concurrent-test"))
        document.current_generation_id = newer.id
        db.commit()
    execute_ingestion(pending["job_id"])
    items = generations(owner, work)
    assert [(g["ordinal"], g["current"]) for g in items if g["ordinal"] in (2, 99)] == [(2, False), (99, True)]
    assert next(g for g in items if g["ordinal"] == 2)["status"] == "available"
