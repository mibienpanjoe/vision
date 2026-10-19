import json
from pathlib import Path

import pytest
from app.core.errors import PublicError
from app.services.ingestion.text_adapter import parse_text

FIXTURE = Path(__file__).parent / "fixtures/narrative"


def test_parser_matches_every_annotated_source_paragraph_and_chapter():
    data = (FIXTURE / "story.md").read_bytes()
    expected = json.loads((FIXTURE / "expected.json").read_text())
    parsed = parse_text(data, "md")
    assert len(parsed.chapters) == 5
    assert len(parsed.passages) == len(expected["passages"])
    for actual, annotation in zip(parsed.passages, expected["passages"], strict=True):
        assert actual.text == annotation["text"]
        assert (actual.start, actual.end, actual.chapter) == (annotation["source_start"], annotation["source_end"], annotation["chapter"])
        assert data.decode()[actual.start:actual.end] == actual.text
    assert parsed.warnings == ()


def test_unicode_crlf_and_dialogue_remain_exact():
    text = "é🦊é\r\nspoke here.\r\n\r\n\"No,\" she replied.\r\n"
    parsed = parse_text(text.encode(), "txt")
    assert [p.text for p in parsed.passages] == ["é🦊é\r\nspoke here.", '\"No,\" she replied.']
    assert all(text[p.start:p.end] == p.text for p in parsed.passages)
    assert all(p.chapter is None for p in parsed.passages)
    assert "chapter_structure_unavailable" in parsed.warnings


def test_fenced_heading_does_not_invent_a_chapter():
    parsed = parse_text(b"# Title\n\n```md\n## Chapter 9\n```\n\nA paragraph.", "md")
    assert parsed.chapters == ()
    assert all(p.chapter is None for p in parsed.passages)


def test_oversized_paragraph_and_heading_only_sources_are_explicit_failures():
    for source in (b"a" * 16385, b"# Title\n\n## Chapter 1\n"):
        with pytest.raises(PublicError):
            parse_text(source, "md")
