"""Idempotent text parsing under one durable SQL outcome transaction."""

import hashlib
import uuid
from datetime import UTC, datetime

from app.core.errors import PublicError
from app.core.storage import PrivateSources
from app.db.session import configured_engine
from app.models.passages import Chapter, Passage
from app.models.works import Document, IngestionJob, Work
from app.services.ingestion.text_adapter import PARSER_REVISION, parse_text
from sqlalchemy import select
from sqlalchemy.orm import Session


def execute_ingestion(job_id: str) -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Database configuration required")
    try:
        with Session(engine) as db, db.begin():
            job = db.scalar(select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id)).with_for_update())
            if job is None or job.status != "queued":
                return
            document = db.get(Document, job.document_id)
            work = db.get(Work, document.work_id)
            if work is None:
                return
            job.attempts += 1
            try:
                if job.processing_version != PARSER_REVISION:
                    raise PublicError(422, "UNSUPPORTED_PARSER_VERSION", "Parser revision is not supported.")
                data = PrivateSources().read(document.source_ref)
                if hashlib.sha256(data).hexdigest() != document.sha256:
                    raise PublicError(422, "SOURCE_INTEGRITY", "Original source integrity check failed.")
                parsed = parse_text(data, document.format)
            except PublicError as error:
                job.status, job.stage, job.error_code = "failed", "failed", error.code
            except (OSError, ValueError):
                job.status, job.stage, job.error_code = "failed", "failed", "SOURCE_STORE_UNAVAILABLE"
            else:
                for chapter in parsed.chapters:
                    db.add(Chapter(id=uuid.uuid5(document.id, f"{PARSER_REVISION}:chapter:{chapter.ordinal}"),
                                   document_id=document.id, parser_revision=PARSER_REVISION,
                                   ordinal=chapter.ordinal, title=chapter.title,
                                   source_start=chapter.start, source_end=chapter.end))
                db.flush()
                for passage in parsed.passages:
                    db.add(Passage(id=uuid.uuid5(document.id, f"{PARSER_REVISION}:passage:{passage.ordinal}"),
                        document_id=document.id, parser_revision=PARSER_REVISION, ordinal=passage.ordinal,
                        chapter_ordinal=passage.chapter, text=passage.text,
                        source_start=passage.start, source_end=passage.end,
                        previous_ordinal=passage.ordinal - 1 if passage.ordinal else None,
                        next_ordinal=passage.ordinal + 1 if passage.ordinal + 1 < len(parsed.passages) else None))
                job.status, job.stage, job.warnings = "succeeded", "parsed", list(parsed.warnings)
            job.completed_at = datetime.now(UTC)
    finally:
        engine.dispose()
