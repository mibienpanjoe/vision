import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.core.errors import PublicError
from app.services.ingestion.inputs import validate_source
from app.services.ingestion.pdf_adapter import PDF_REVISION, parse_pdf

FORMATS = Path(__file__).parent / "fixtures/formats"
NARRATIVE = Path(__file__).parent / "fixtures/narrative"


def words(value):
    return re.sub(r"\s+", " ", value).strip()


@pytest.fixture(scope="module")
def story():
    return parse_pdf((FORMATS / "story.pdf").read_bytes())


def test_pdf_passages_keep_reading_order_chapters_and_pages(story):
    parsed, text = story.parsed, story.text
    assert PDF_REVISION == "pdf-docling-v1"
    assert [chapter.title for chapter in parsed.chapters] == [
        "Chapter 1 — Before the war", "Chapter 2 — The war", "Chapter 3 — The road and the return",
        "Chapter 4 — Conflicting records", "Chapter 5 — A late revelation"]
    for chapter in parsed.chapters:
        assert text[chapter.start:chapter.end] == chapter.title
    for passage in parsed.passages:
        assert text[passage.start:passage.end] == passage.text
        # The fixture starts every chapter on its own page.
        assert passage.locator["pages"] == [passage.chapter]
        for page, left, top, right, bottom in passage.locator["boxes"]:
            # A5 is 420 x 595 points; boxes are top-left origin within the page.
            assert page == passage.chapter and 0 <= left < right <= 420 and 0 <= top < bottom <= 595
    assert "inferred_paragraphs" in parsed.warnings
    assert "pages_without_text" not in parsed.warnings
    assert not any(re.search(r"\w [.,]", passage.text) for passage in parsed.passages)


def test_annotated_sentences_resolve_to_the_page_of_their_chapter(story):
    expected = json.loads((NARRATIVE / "expected.json").read_text())
    by_page = {}
    for passage in story.parsed.passages:
        page = passage.locator["pages"][0]
        by_page[page] = words(by_page.get(page, "") + " " + passage.text)
    # Layout extraction may split, merge or space punctuation differently from
    # the authored paragraphs; each annotated sentence must still be found
    # verbatim in its chapter's page text, and on no other page.
    for annotation in expected["passages"]:
        for sentence in re.findall(r"[^.!?]+[.!?]\"?", annotation["text"]):
            # Chromium's text layer itself drops this line-break hyphen.
            needle = words(sentence).rstrip(".!?\"").replace("left-cheek", "leftcheek")
            pages = [page for page, text in by_page.items() if needle in text]
            assert pages == [annotation["chapter"]], (needle, pages)


def test_text_layer_absence_and_encryption_are_explicit():
    with pytest.raises(PublicError) as outlined:
        parse_pdf((FORMATS / "outlined.pdf").read_bytes())
    assert outlined.value.code == "TEXT_LAYER_UNAVAILABLE"
    with pytest.raises(PublicError) as encrypted:
        parse_pdf((FORMATS / "encrypted.pdf").read_bytes())
    assert encrypted.value.code == "PDF_ENCRYPTED"


def test_pdf_input_boundary_rejects_disguises_and_malformed_files():
    with pytest.raises(PublicError):
        validate_source(b"plain text pretending", "pdf")
    with pytest.raises(PublicError):
        validate_source((FORMATS / "story.pdf").read_bytes(), "txt")
    assert validate_source(b"%PDF-1.7\n", "pdf") is None
    with pytest.raises(PublicError) as malformed:
        parse_pdf(b"%PDF-1.7\nnot really a document")
    assert malformed.value.code == "INVALID_SOURCE"


def test_page_budget_fails_before_layout_work(monkeypatch):
    from app.services.ingestion import pdf_adapter

    monkeypatch.setattr(pdf_adapter, "MAX_PAGES", 2)
    with pytest.raises(PublicError) as limited:
        parse_pdf((FORMATS / "story.pdf").read_bytes())
    assert limited.value.code == "PARSER_LIMIT"


def test_document_timeout_is_partial_extraction_not_success(monkeypatch):
    from app.services.ingestion import pdf_adapter

    monkeypatch.setattr(pdf_adapter, "DOCUMENT_SECONDS", 0.01)
    pdf_adapter.converter.cache_clear()
    try:
        with pytest.raises(PublicError) as partial:
            parse_pdf((FORMATS / "story.pdf").read_bytes())
    finally:
        pdf_adapter.converter.cache_clear()
    assert partial.value.code == "PARTIAL_EXTRACTION"


def test_missing_models_fail_without_downloading(monkeypatch, tmp_path):
    monkeypatch.setenv("VISION_DOCLING_ARTIFACTS", str(tmp_path / "absent"))
    with pytest.raises(PublicError) as unavailable:
        parse_pdf((FORMATS / "story.pdf").read_bytes())
    assert unavailable.value.code == "PARSER_UNAVAILABLE"


@pytest.mark.integration
def test_uploaded_pdf_parses_through_worker_and_cites_its_pages(database, monkeypatch, tmp_path):
    from app.core.passwords import hash_password
    from app.main import create_app
    from app.models.access import Principal
    from app.models.passages import Chapter, Passage
    from app.services.ingestion.parse import execute_ingestion
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    origin = {"Origin": "http://127.0.0.1:3000"}
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    with Session(database) as db:
        db.add(Principal(username="pdf_reader", password_hash=hash_password("synthetic pdf test passphrase")))
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "pdf_reader", "password": "synthetic pdf test passphrase"},
                           headers=origin).status_code == 200

        def upload(name, key):
            return client.post("/v1/works", data={"title": name, "format": "pdf"},
                               files={"file": ("book.pdf", (FORMATS / name).read_bytes())},
                               headers={**origin, "Idempotency-Key": key})

        disguised = client.post("/v1/works", data={"title": "Text", "format": "pdf"},
                                files={"file": ("book.pdf", b"plain text")}, headers={**origin, "Idempotency-Key": "fake"})
        assert disguised.status_code == 422
        outcomes = {}
        for name in ("story.pdf", "outlined.pdf", "encrypted.pdf"):
            accepted = upload(name, name.replace(".", "-")).json()
            assert accepted["work"]["format"] == "pdf"
            execute_ingestion(accepted["job"]["id"])
            job = client.get(f"/v1/works/{accepted['work']['id']}/ingestions/{accepted['job']['id']}").json()
            outcomes[name] = (job["status"], job["error_code"], accepted)
        assert outcomes["outlined.pdf"][:2] == ("failed", "TEXT_LAYER_UNAVAILABLE")
        assert outcomes["encrypted.pdf"][:2] == ("failed", "PDF_ENCRYPTED")
        assert outcomes["story.pdf"][:2] == ("succeeded", None)
        work = outcomes["story.pdf"][2]["work"]
        with Session(database) as db:
            passages = list(db.scalars(select(Passage).where(Passage.document_id == work["document_id"]).order_by(Passage.ordinal)))
            chapters = list(db.scalars(select(Chapter).where(Chapter.document_id == work["document_id"]).order_by(Chapter.ordinal)))
        assert {p.parser_revision for p in passages} == {PDF_REVISION}
        assert {p.normalization_revision for p in passages} == {"pdf-punct-v1"}
        quote = "Arthur opened the visitor's mask"
        late = passages[-1]
        start = late.text.index(quote)
        request = {"span": {"document_revision_id": work["document_id"], "passage_id": str(late.id),
                            "start": start, "end": start + len(quote), "quote": quote},
                   "parser_revision": PDF_REVISION, "reading_boundary": {"mode": "whole_book"}}
        evidence = client.post(f"/v1/works/{work['id']}/evidence", json=request, headers=origin)
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["pages"] == [5]
        request["reading_boundary"] = {"mode": "through_chapter", "chapter_id": str(chapters[1].id)}
        assert client.post(f"/v1/works/{work['id']}/evidence", json=request, headers=origin).status_code == 404

        redis_url = os.environ.get("VISION_TEST_REDIS_URL")
        if not redis_url:
            pytest.skip("Set VISION_TEST_REDIS_URL for the real PDF worker run")
        monkeypatch.setenv("REDIS_URL", redis_url)
        monkeypatch.setenv("VISION_QUEUE_NAMESPACE", "vision_test_" + uuid.uuid4().hex)
        accepted = upload("story.pdf", "pdf-worker").json()
        endpoint = f"/v1/works/{accepted['work']['id']}/ingestions/{accepted['job']['id']}"
        api = Path(__file__).parents[1]
        with (tmp_path / "pdf-worker.log").open("w") as log:
            worker = subprocess.Popen([str(api / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1", "--threads", "1"],
                                      cwd=api, env=os.environ.copy(), stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(600):
                    job = client.get(endpoint).json()
                    if job["status"] in {"succeeded", "failed"}:
                        break
                    time.sleep(0.2)
            finally:
                worker.terminate()
                worker.wait(timeout=30)
        assert (job["status"], job["attempts"]) == ("succeeded", 1), job
        assert "inferred_paragraphs" in job["warnings"]
