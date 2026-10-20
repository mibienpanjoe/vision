"""Resolve immutable source spans only after owner/revision/cutoff checks."""

import uuid

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.passages import Chapter, Passage
from app.models.works import Document, Work
from app.schemas.evidence import EvidenceView
from sqlalchemy import select


def not_found():
    return PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")


def section_of(locator):
    if "section" not in locator:
        return None
    return locator["section"] + (f"#{locator['anchor']}" if locator.get("anchor") else "")


def resolve_evidence(db, actor, work_id, body):
    owned_object(db, Work, work_id, actor)
    try:
        document_id = uuid.UUID(body.span.document_revision_id)
        passage_id = uuid.UUID(body.span.passage_id)
    except ValueError:
        raise not_found() from None
    document = db.scalar(select(Document).where(Document.id == document_id, Document.work_id == work_id))
    passage = db.scalar(select(Passage).where(Passage.id == passage_id, Passage.document_id == document_id,
                                             Passage.parser_revision == body.parser_revision))
    if document is None or passage is None:
        raise not_found()
    chapter = db.scalar(select(Chapter).where(Chapter.document_id == document_id,
                        Chapter.parser_revision == passage.parser_revision, Chapter.ordinal == passage.chapter_ordinal))
    if body.reading_boundary.mode == "through_chapter":
        try:
            cutoff_id = uuid.UUID(body.reading_boundary.chapter_id)
        except ValueError:
            raise not_found() from None
        cutoff = db.scalar(select(Chapter).where(Chapter.id == cutoff_id, Chapter.document_id == document_id,
                                               Chapter.parser_revision == body.parser_revision))
        if cutoff is None or chapter is None or chapter.ordinal > cutoff.ordinal:
            raise not_found()
    try:
        body.span.validate_text(passage.text)
    except ValueError:
        raise PublicError(422, "EVIDENCE_MISMATCH", "Source span does not match the retained text.") from None
    locator = passage.locator or {}
    start = max(0, body.span.start - body.context_before)
    end = min(len(passage.text), body.span.end + body.context_after)
    return EvidenceView(span=body.span, parser_revision=passage.parser_revision,
                        excerpt=passage.text[start:end], excerpt_start=start,
                        highlight_start=body.span.start - start, highlight_end=body.span.end - start,
                        original_start=passage.source_start + body.span.start,
                        original_end=passage.source_start + body.span.end,
                        chapter_id=chapter.id if chapter is not None else None,
                        pages=locator.get("pages"), section=section_of(locator))
