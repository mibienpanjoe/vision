"""Bounded chapter-number catalog; titles would disclose future narrative text."""

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.generations import SourceGeneration
from app.models.passages import Chapter
from app.models.works import Work
from app.schemas.works import ChapterNumber, ChapterPage
from app.services.ingestion.upload import document_for
from sqlalchemy import select


def list_chapters(db, actor, work_id, after, limit):
    document = document_for(db, owned_object(db, Work, work_id, actor))
    generation = db.get(SourceGeneration, document.current_generation_id) if document.current_generation_id else None
    if generation is None:
        raise PublicError(409, "SOURCE_NOT_READY", "Source parsing is not complete.")
    chapters = list(db.scalars(select(Chapter).where(
        Chapter.document_id == document.id, Chapter.parser_revision == generation.parser_revision,
        Chapter.ordinal > after).order_by(Chapter.ordinal).limit(limit + 1)))
    return ChapterPage(document_revision_id=document.id, generation_id=generation.id,
                       parser_revision=generation.parser_revision,
                       items=[ChapterNumber(id=c.id, ordinal=c.ordinal) for c in chapters[:limit]],
                       next_after=chapters[limit - 1].ordinal if len(chapters) > limit else None)
