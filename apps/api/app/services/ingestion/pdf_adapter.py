"""Docling PDF extraction with page anchors, an offline model and no OCR.

PDF has no authored paragraph text to slice. Spans index this parser revision's
canonical text: extracted blocks in reading order joined by blank lines.
"""

import os
import re
import threading
from dataclasses import dataclass
from functools import cache
from io import BytesIO
from pathlib import Path

from app.core.errors import PublicError
from app.services.ingestion.text_adapter import (
    CHAPTER,
    MAX_CODEPOINTS,
    MAX_PASSAGE,
    MAX_PASSAGES,
    ParsedChapter,
    ParsedPassage,
    ParsedText,
)

PDF_REVISION = "pdf-docling-v1"
NORMALIZATION = "pdf-punct-v1"
MAX_PAGES = 2000
DOCUMENT_SECONDS = 600
SEPARATOR = "\n\n"
HEADINGS = {"title", "section_header"}
TEXT_LABELS = {"text", "paragraph", "list_item", "footnote", "caption", "code", "formula"}
CONVERSION = threading.Lock()
# Docling joins a line-final period or comma as a separate cell ("roof ."). Only
# these two are rejoined: French typography legitimately spaces "?!;:".
DETACHED = re.compile(r"(?<=\S) (?=[.,](?:\s|$|[\"'”’)]))")


@dataclass(frozen=True)
class ParsedPdf:
    parsed: ParsedText
    text: str


def artifacts_path():
    # The checkout default is resolved only without the setting; packaged images have no repository above /app.
    configured = os.environ.get("VISION_DOCLING_ARTIFACTS")
    return Path(configured) if configured else Path(__file__).parents[5] / ".local/docling-models"


@cache
def converter(artifacts):
    # Imported lazily: the API process never loads the layout model.
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # An explicit artifacts path keeps Docling offline. The pypdfium2 backend
    # preserved reading order where docling-parse moved lines across paragraphs.
    options = PdfPipelineOptions(artifacts_path=artifacts, do_ocr=False, do_table_structure=False,
                                 document_timeout=DOCUMENT_SECONDS, enable_remote_services=False)
    return DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options, backend=PyPdfiumDocumentBackend)})


def count_pages(data):
    import pypdfium2

    try:
        document = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as error:
        if "password" in str(error).lower():
            raise PublicError(422, "PDF_ENCRYPTED", "Encrypted PDFs are not supported.") from None
        raise PublicError(422, "INVALID_SOURCE", "Source is not a readable PDF.") from None
    try:
        return len(document)
    finally:
        document.close()


def locate(item, pages):
    # Boxes use a top-left origin in PDF points: [page, left, top, right, bottom].
    boxes = []
    for prov in item.prov:
        box = prov.bbox.to_top_left_origin(pages[prov.page_no].size.height)
        boxes.append([prov.page_no, *(round(value, 1) for value in box.as_tuple())])
    return {"pages": sorted({prov.page_no for prov in item.prov}), "boxes": boxes}


def parse_pdf(data: bytes) -> ParsedPdf:
    if count_pages(data) > MAX_PAGES:
        raise PublicError(422, "PARSER_LIMIT", "Source exceeds the PDF page budget.")
    artifacts = artifacts_path()
    if not artifacts.is_dir():
        raise PublicError(503, "PARSER_UNAVAILABLE", "PDF parser models are not installed.", True)
    from docling.datamodel.base_models import ConversionStatus, DocumentStream

    with CONVERSION:
        result = converter(str(artifacts)).convert(
            DocumentStream(name="source.pdf", stream=BytesIO(data)), raises_on_error=False,
            max_num_pages=MAX_PAGES, max_file_size=len(data))
    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        raise PublicError(422, "PARTIAL_EXTRACTION", "Only part of the PDF could be extracted.")
    if result.status != ConversionStatus.SUCCESS:
        raise PublicError(422, "INVALID_SOURCE", "Source is not a readable PDF.")
    blocks, chapters, passages, chapter, skipped = [], [], [], None, False
    offset = 0
    covered = set()
    for item, _level in result.document.iterate_items():
        label, value = str(item.label), DETACHED.sub("", getattr(item, "text", "").strip())
        if label not in HEADINGS | TEXT_LABELS or not value:
            skipped = skipped or label in {"picture", "table", "chart"}
            continue
        covered.update(prov.page_no for prov in item.prov)
        start, end = offset, offset + len(value)
        if label in HEADINGS:
            if CHAPTER.fullmatch(value):
                if len(chapters) >= 2000:
                    raise PublicError(422, "PARSER_LIMIT", "Source exceeds the chapter budget.")
                chapter = len(chapters) + 1
                chapters.append(ParsedChapter(chapter, value, start, end, locate(item, result.document.pages)))
        else:
            if end - start > MAX_PASSAGE or len(passages) >= MAX_PASSAGES:
                raise PublicError(422, "PARSER_LIMIT", "Source exceeds the passage budget.")
            passages.append(ParsedPassage(len(passages), chapter, start, end, value, locate(item, result.document.pages)))
        blocks.append(value)
        offset = end + len(SEPARATOR)
        if offset > MAX_CODEPOINTS:
            raise PublicError(422, "PARSER_LIMIT", "Source exceeds the text parser budget.")
    if not passages:
        raise PublicError(422, "TEXT_LAYER_UNAVAILABLE", "PDF has no extractable text layer; OCR is not enabled.")
    warnings = ["inferred_paragraphs"]
    if not chapters:
        warnings.append("chapter_structure_unavailable")
    elif any(passage.chapter is None for passage in passages):
        warnings.append("unassigned_preamble")
    if set(range(1, len(result.document.pages) + 1)) - covered:
        warnings.append("pages_without_text")
    if skipped:
        warnings.append("non_text_content_skipped")
    return ParsedPdf(ParsedText(tuple(chapters), tuple(passages), tuple(warnings)), SEPARATOR.join(blocks))
