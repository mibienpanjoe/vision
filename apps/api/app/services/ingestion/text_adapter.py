"""Versioned paragraph extraction without rendering or normalizing source text."""

import re
from dataclasses import dataclass

from app.core.errors import PublicError
from app.services.ingestion.inputs import validate_text_source

PARSER_REVISION = "text-v1"
MAX_CODEPOINTS = 2_000_000
MAX_PASSAGE = 16384
MAX_PASSAGES = 20000
BLANK_LINE = re.compile(r"\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*")
CHAPTER = re.compile(r"Chapter\s+\d+(?:\b.*)?$", re.I)


@dataclass(frozen=True)
class ParsedChapter:
    ordinal: int
    title: str
    start: int
    end: int


@dataclass(frozen=True)
class ParsedPassage:
    ordinal: int
    chapter: int | None
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ParsedText:
    chapters: tuple[ParsedChapter, ...]
    passages: tuple[ParsedPassage, ...]
    warnings: tuple[str, ...]


def parse_text(data: bytes, source_format: str) -> ParsedText:
    if source_format not in {"txt", "md"}:
        raise PublicError(422, "UNSUPPORTED_FORMAT", "Source format is not supported.")
    text = validate_text_source(data)
    if len(text) > MAX_CODEPOINTS:
        raise PublicError(422, "PARSER_LIMIT", "Source exceeds the text parser budget.")
    chapters, passages = [], []
    chapter = None
    fenced = None
    section_start = 0

    def append_paragraphs(start, end):
        cursor = start
        ranges = [(match.start(), match.end()) for match in BLANK_LINE.finditer(text, start, end)]
        for boundary_start, boundary_end in [*ranges, (end, end)]:
            raw = text[cursor:boundary_start]
            left = len(raw) - len(raw.lstrip(" \t\r\n\ufeff"))
            right = len(raw.rstrip(" \t\r\n"))
            if right > left:
                source_start, source_end = cursor + left, cursor + right
                if source_end - source_start > MAX_PASSAGE or len(passages) >= MAX_PASSAGES:
                    raise PublicError(422, "PARSER_LIMIT", "Source exceeds the passage budget.")
                passages.append(ParsedPassage(len(passages), chapter, source_start, source_end, text[source_start:source_end]))
            cursor = boundary_end

    offset = 0
    for line in text.splitlines(keepends=True):
        value = line.rstrip("\r\n")
        stripped = value.lstrip(" ")
        fence = re.match(r"(`{3,}|~{3,})", stripped) if source_format == "md" else None
        if fence is not None:
            marker = fence.group(1)
            if fenced is None:
                fenced = marker
            elif marker[0] == fenced[0] and len(marker) >= len(fenced):
                fenced = None
        heading = re.match(r"^#{1,6}[ \t]+(.+?)\s*#*\s*$", value) if source_format == "md" and fenced is None else None
        title = heading.group(1) if heading else value.strip()
        chapter_heading = CHAPTER.fullmatch(title) if fenced is None and (source_format == "txt" or heading is not None) else None
        if heading is not None or chapter_heading is not None:
            append_paragraphs(section_start, offset)
            if chapter_heading is not None:
                if len(chapters) >= 2000:
                    raise PublicError(422, "PARSER_LIMIT", "Source exceeds the chapter budget.")
                chapter = len(chapters) + 1
                chapters.append(ParsedChapter(chapter, title, offset, offset + len(value)))
            section_start = offset + len(line)
        offset += len(line)
    append_paragraphs(section_start, len(text))
    if not passages:
        raise PublicError(422, "NO_PASSAGES", "Source contains no supported paragraphs.")
    warnings = []
    if not chapters:
        warnings.append("chapter_structure_unavailable")
    elif any(p.chapter is None for p in passages):
        warnings.append("unassigned_preamble")
    if fenced is not None:
        warnings.append("unclosed_markdown_fence")
    return ParsedText(tuple(chapters), tuple(passages), tuple(warnings))
