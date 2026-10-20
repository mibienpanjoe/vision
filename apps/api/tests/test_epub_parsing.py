import json
from pathlib import Path

import pytest
from app.core.errors import PublicError
from app.services.ingestion import epub_adapter
from app.services.ingestion.epub_adapter import EPUB_REVISION, parse_epub
from app.services.ingestion.inputs import validate_source
from epub_builder import CONTAINER, build, flag_encrypted

NARRATIVE = Path(__file__).parent / "fixtures/narrative"


def failure(data):
    with pytest.raises(PublicError) as error:
        parse_epub(data)
    return error.value.code


def test_spine_sections_map_to_exact_passages_chapters_and_anchors():
    result = parse_epub(build())
    parsed, expected = result.parsed, json.loads((NARRATIVE / "expected.json").read_text())
    assert EPUB_REVISION == "epub-xhtml-v1"
    assert [chapter.title for chapter in parsed.chapters] == [
        "Chapter 1 — Before the war", "Chapter 2 — The war", "Chapter 3 — The road and the return",
        "Chapter 4 — Conflicting records", "Chapter 5 — A late revelation"]
    # Authored paragraphs survive exactly once HTML whitespace is collapsed.
    assert [(p.text, p.chapter) for p in parsed.passages] == [(a["text"], a["chapter"]) for a in expected["passages"]]
    for passage in parsed.passages:
        assert result.text[passage.start:passage.end] == passage.text
        section = f"OEBPS/text/chapter{passage.chapter}.xhtml"
        assert passage.locator["section"] == section and passage.locator["spine"] == passage.chapter
        assert passage.locator["anchor"].startswith(f"ch{passage.chapter}-p")
    for chapter in parsed.chapters:
        assert result.text[chapter.start:chapter.end] == chapter.title
        assert chapter.locator["anchor"] == f"ch{chapter.ordinal}"
    for span in expected["spans"]:
        passage = parsed.passages[int(span["passage_id"][1:]) - 1]
        assert passage.text[span["start"]:span["end"]] == span["quote"]
    # Title page image, stylesheet, script and nav are never treated as text.
    assert "script" not in result.text and "Contents" not in result.text
    assert parsed.warnings == ("non_text_content_skipped",)


def test_line_breaks_entities_and_inline_markup_are_explicit():
    body = '<p id="a">One&#160;<em>two</em><br/>three&amp;four</p><div>Loose <b>div</b> text</div>'
    data = build({"OEBPS/text/chapter1.xhtml": f'<html xmlns="http://www.w3.org/1999/xhtml"><body><h2>Chapter 1</h2>{body}</body></html>'})
    passages = parse_epub(data).parsed.passages
    assert passages[0].text == "One two\nthree&four"
    assert passages[0].locator["anchor"] == "a"
    assert passages[1].text == "Loose div text" and passages[1].locator["anchor"] is None


def test_unsafe_container_paths_and_layout_fail_before_parsing():
    assert failure(build({"../escape.xhtml": "x"})) == "EPUB_UNSAFE_PATH"
    assert failure(build({"/etc/passwd": "x"})) == "EPUB_UNSAFE_PATH"
    assert failure(build({"OEBPS\\text\\win.xhtml": "x"})) == "EPUB_UNSAFE_PATH"
    escaped = build({"META-INF/container.xml": CONTAINER.replace("OEBPS/content.opf", "../content.opf")})
    assert failure(escaped) == "EPUB_UNSAFE_PATH"
    evil = '<item id="evil" href="{}" media-type="application/xhtml+xml"/>'
    outside = build(items=[evil.format("../../evil.xhtml")], spine=['<itemref idref="evil"/>'])
    assert failure(outside) == "EPUB_UNSAFE_PATH"
    missing = build(items=[evil.format("text/missing.xhtml")], spine=['<itemref idref="evil"/>'])
    assert failure(missing) == "INVALID_SOURCE"
    assert failure(build(mimetype=b"application/zip")) == "INVALID_SOURCE"
    assert failure(build({"META-INF/container.xml": None})) == "INVALID_SOURCE"
    assert failure(b"PK\x03\x04 not a zip archive") == "INVALID_SOURCE"


def test_entity_expansion_and_external_dtd_are_refused():
    bomb = ('<?xml version="1.0"?><!DOCTYPE c [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;">]>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">&b;</container>')
    assert failure(build({"META-INF/container.xml": bomb})) == "INVALID_SOURCE"
    external = ('<?xml version="1.0"?><!DOCTYPE html [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><body><h2>Chapter 1</h2><p>&x;</p></body></html>')
    secret = Path("/etc/hostname").read_text().strip() or "unreachable"
    result = parse_epub(build({"OEBPS/text/chapter1.xhtml": external}))
    assert result.parsed.passages[0].text == "&x;" and secret not in result.text


def test_expansion_entry_count_and_encryption_budgets(monkeypatch):
    monkeypatch.setattr(epub_adapter, "MAX_EXPANDED", 4096)
    assert failure(build({"OEBPS/text/padding.bin": "0" * 8192})) == "PARSER_LIMIT"
    monkeypatch.undo()
    monkeypatch.setattr(epub_adapter, "MAX_ENTRIES", 5)
    assert failure(build()) == "PARSER_LIMIT"
    monkeypatch.undo()
    encryption = ('<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
                  'xmlns:enc="http://www.w3.org/2001/04/xmlenc#"><enc:EncryptedData><enc:CipherData>'
                  '<enc:CipherReference URI="OEBPS/text/chapter1.xhtml"/></enc:CipherData></enc:EncryptedData></encryption>')
    assert failure(build({"META-INF/encryption.xml": encryption})) == "EPUB_ENCRYPTED"
    assert failure(flag_encrypted(build(), "OEBPS/text/chapter2.xhtml")) == "EPUB_ENCRYPTED"


def test_compressed_expansion_is_bounded_per_entry(monkeypatch):
    monkeypatch.setattr(epub_adapter, "MAX_ENTRY", 2048)
    # Highly compressible content: tiny archive, large expansion.
    assert failure(build({"OEBPS/text/chapter1.xhtml": "<p>" + "a" * 100_000 + "</p>"})) == "PARSER_LIMIT"


def test_epub_input_boundary():
    validate_source(build(), "epub")
    with pytest.raises(PublicError):
        validate_source(b"plain text", "epub")
    with pytest.raises(PublicError):
        validate_source(build(), "txt")


@pytest.mark.integration
def test_uploaded_epub_parses_and_cites_its_section(database, monkeypatch, tmp_path):
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
        db.add(Principal(username="epub_reader", password_hash=hash_password("synthetic epub test passphrase")))
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "epub_reader", "password": "synthetic epub test passphrase"},
                           headers=origin).status_code == 200

        def ingest(data, key):
            accepted = client.post("/v1/works", data={"title": "Synthetic EPUB", "format": "epub"},
                                   files={"file": ("book.epub", data)}, headers={**origin, "Idempotency-Key": key}).json()
            execute_ingestion(accepted["job"]["id"])
            job = client.get(f"/v1/works/{accepted['work']['id']}/ingestions/{accepted['job']['id']}").json()
            return accepted["work"], job

        work, job = ingest(build(), "epub-story")
        assert (job["status"], job["warnings"]) == ("succeeded", ["non_text_content_skipped"])
        _, unsafe_job = ingest(build({"../escape.xhtml": "x"}), "epub-unsafe")
        assert (unsafe_job["status"], unsafe_job["error_code"]) == ("failed", "EPUB_UNSAFE_PATH")
        with Session(database) as db:
            passages = list(db.scalars(select(Passage).where(Passage.document_id == work["document_id"]).order_by(Passage.ordinal)))
            chapters = list(db.scalars(select(Chapter).where(Chapter.document_id == work["document_id"]).order_by(Chapter.ordinal)))
        assert {(p.parser_revision, p.normalization_revision) for p in passages} == {(EPUB_REVISION, "html-space-v1")}
        late = passages[-1]
        quote = "I was Wren at ten."
        start = late.text.index(quote)
        request = {"span": {"document_revision_id": work["document_id"], "passage_id": str(late.id),
                            "start": start, "end": start + len(quote), "quote": quote},
                   "parser_revision": EPUB_REVISION, "reading_boundary": {"mode": "whole_book"}}
        evidence = client.post(f"/v1/works/{work['id']}/evidence", json=request, headers=origin)
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["section"] == "OEBPS/text/chapter5.xhtml#ch5-p2"
        assert evidence.json()["pages"] is None
        request["reading_boundary"] = {"mode": "through_chapter", "chapter_id": str(chapters[3].id)}
        assert client.post(f"/v1/works/{work['id']}/evidence", json=request, headers=origin).status_code == 404
