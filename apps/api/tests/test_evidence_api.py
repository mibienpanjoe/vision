import json
import uuid
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.passages import Chapter, Passage
from app.services.ingestion.parse import execute_ingestion
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


@pytest.fixture
def evidence_readers(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    password = "synthetic evidence test passphrase"
    with Session(database) as db:
        db.add_all([Principal(username=name, password_hash=hash_password(password)) for name in ("evidence_alice", "evidence_bruno")])
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as alice, TestClient(create_app(), base_url="http://127.0.0.1") as bruno:
        for client, name in [(alice, "evidence_alice"), (bruno, "evidence_bruno")]:
            assert client.post("/v1/auth/login", json={"username": name, "password": password}, headers=ORIGIN).status_code == 200
        fixture = Path(__file__).parent / "fixtures/narrative"
        source = (fixture / "story.md").read_bytes()
        accepted = alice.post("/v1/works", data={"title": "Evidence synthetic", "format": "md"},
                              files={"file": ("synthetic.md", source)},
                              headers={**ORIGIN, "Idempotency-Key": "evidence-source"}).json()
        execute_ingestion(accepted["job"]["id"])
        with Session(database) as db:
            passages = list(db.scalars(select(Passage).order_by(Passage.ordinal)))
            chapters = list(db.scalars(select(Chapter).order_by(Chapter.ordinal)))
            db.expunge_all()
        yield alice, bruno, accepted["work"]["id"], passages, chapters, json.loads((fixture / "expected.json").read_text())


def request_for(passage, start, end, boundary=None):
    return {"span": {"document_revision_id": str(passage.document_id), "passage_id": str(passage.id),
                     "start": start, "end": end, "quote": passage.text[start:end]},
            "parser_revision": passage.parser_revision, "reading_boundary": boundary or {"mode": "whole_book"},
            "context_before": 100, "context_after": 100}


def test_exact_annotated_spans_and_bounded_unicode_context(evidence_readers):
    alice, _, work, passages, _, corpus = evidence_readers
    for expected in corpus["spans"]:
        index = int(expected["passage_id"][1:]) - 1
        request = request_for(passages[index], expected["start"], expected["end"])
        response = alice.post(f"/v1/works/{work}/evidence", json=request, headers=ORIGIN)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["span"]["quote"] == expected["quote"]
        assert result["excerpt"][result["highlight_start"]:result["highlight_end"]] == expected["quote"]
        assert result["original_start"] == passages[index].source_start + expected["start"]
        assert len(result["excerpt"]) <= 2200


def test_owner_revision_parser_and_chapter_cutoff_fail_closed(evidence_readers):
    alice, bruno, work, passages, chapters, _ = evidence_readers
    request = request_for(passages[0], 0, 5, {"mode": "through_chapter", "chapter_id": str(chapters[0].id)})
    endpoint = f"/v1/works/{work}/evidence"
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 200
    assert bruno.post(endpoint, json=request, headers=ORIGIN).status_code == 404
    future = request_for(passages[-1], 0, 5, request["reading_boundary"])
    assert alice.post(endpoint, json=future, headers=ORIGIN).status_code == 404
    request["span"]["document_revision_id"] = str(uuid.uuid4())
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 404
    request = request_for(passages[0], 0, 5)
    request["parser_revision"] = "other-version"
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 404
    request = request_for(passages[0], 0, 5, {"mode": "through_chapter", "chapter_id": str(uuid.uuid4())})
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 404


def test_bad_spans_context_bounds_and_body_size_fail_safely(evidence_readers):
    alice, _, work, passages, _, _ = evidence_readers
    endpoint = f"/v1/works/{work}/evidence"
    request = request_for(passages[1], 0, 5)
    request["span"]["quote"] = "wrong"
    response = alice.post(endpoint, json=request, headers=ORIGIN)
    assert response.status_code == 422 and "wrong" not in response.text
    request = request_for(passages[1], 0, 1)
    request["span"].update(start=9999, end=10000, quote="x")
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 422
    request = request_for(passages[1], 0, 1)
    request["context_after"] = 501
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 422
    request = request_for(passages[1], 0, 1)
    request["owner_id"] = str(uuid.uuid4())
    assert alice.post(endpoint, json=request, headers=ORIGIN).status_code == 422
    assert alice.post(endpoint, content=iter([b"x" * 4096] * 9), headers={**ORIGIN, "Content-Type": "application/json"}).status_code == 413


def test_unassigned_preamble_is_unavailable_under_a_chapter_cutoff(evidence_readers, database):
    alice, _, _, _, _, _ = evidence_readers
    accepted = alice.post("/v1/works", data={"title": "Unassigned preamble", "format": "md"},
                          files={"file": ("preamble.md", b"Unassigned preamble.\n\n## Chapter 1\n\nAssigned paragraph.")},
                          headers={**ORIGIN, "Idempotency-Key": "preamble"}).json()
    execute_ingestion(accepted["job"]["id"])
    with Session(database) as db:
        document_id = uuid.UUID(accepted["work"]["document_id"])
        passage = db.scalar(select(Passage).where(Passage.document_id == document_id, Passage.ordinal == 0))
        cutoff = db.scalar(select(Chapter).where(Chapter.document_id == document_id))
        body = request_for(passage, 0, 5)
        endpoint = f"/v1/works/{accepted['work']['id']}/evidence"
        assert alice.post(endpoint, json=body, headers=ORIGIN).status_code == 200
        body["reading_boundary"] = {"mode": "through_chapter", "chapter_id": str(cutoff.id)}
        assert alice.post(endpoint, json=body, headers=ORIGIN).status_code == 404
