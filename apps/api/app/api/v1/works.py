"""Authenticated, bounded multipart ingestion and private library reads."""

import asyncio
import uuid
from typing import Annotated, Literal

from app.core.errors import PublicError
from app.core.security import ActorScope, current_actor, database_session, owned_object
from app.core.storage import PrivateSources
from app.models.works import IngestionJob, Work
from app.schemas.works import (
    ChapterPage,
    GenerationPage,
    GenerationView,
    IngestionView,
    LibraryPage,
    UploadAccepted,
    UploadMetadata,
    WorkDeletionView,
    WorkView,
)
from app.services.ingestion.chapters import list_chapters
from app.services.ingestion.inputs import MAX_SOURCE_BYTES, UPLOAD_SECONDS
from app.services.ingestion.jobs import mutate_job
from app.services.ingestion.reprocess import create_generation, list_generations
from app.services.ingestion.upload import (
    create_work,
    document_for,
    ingestion_view,
    work_view,
)
from app.services.works.deletion import request_deletion
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

router = APIRouter(prefix="/v1/works", tags=["library"])
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]
UPLOAD_SCHEMA = UploadMetadata.model_json_schema()
UPLOAD_SCHEMA["properties"]["file"] = {"type": "string", "format": "binary"}
UPLOAD_SCHEMA["required"] = ["file"]

Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


def storage_error():
    return PublicError(503, "SOURCE_STORE_UNAVAILABLE", "Source storage is unavailable.", True)


@router.post("", status_code=202, response_model=UploadAccepted,
             openapi_extra={"requestBody": {"required": True, "content": {
                 "multipart/form-data": {"schema": UPLOAD_SCHEMA}}}})
async def upload(request: Request, key: Key, actor: Actor, db: Database):
    if request.query_params:
        raise PublicError(422, "INVALID_REQUEST", "Upload metadata belongs in the multipart form.")
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise PublicError(415, "UNSUPPORTED_MEDIA_TYPE", "Use a multipart upload.")
    # Authenticate before consuming a body. Count actual received bytes rather
    # than trusting Content-Length; total multipart overhead is bounded too.
    body = bytearray()
    try:
        async with asyncio.timeout(UPLOAD_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_SOURCE_BYTES + 65536:
                    raise PublicError(413, "SOURCE_TOO_LARGE", "Source exceeds the upload limit.")
                body.extend(chunk)
    except TimeoutError:
        raise PublicError(408, "SOURCE_TIMEOUT", "Upload transfer timed out.") from None

    async def receive():
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    bounded = Request(request.scope, receive)
    async with bounded.form(max_files=1, max_fields=2, max_part_size=4096) as form:
        if "file" not in form or set(form) - {"file", "format", "title"} or len(form.multi_items()) != len(form):
            raise PublicError(422, "INVALID_REQUEST", "Upload requires one file and optional title and format.")
        file = form["file"]
        if not isinstance(file, UploadFile):
            raise PublicError(422, "INVALID_REQUEST", "Upload requires one source file.")
        try:
            metadata = UploadMetadata.model_validate({"title": form.get("title"), "format": form.get("format")})
        except ValidationError:
            raise PublicError(422, "INVALID_REQUEST", "Invalid upload metadata.") from None
        data = await file.read(MAX_SOURCE_BYTES + 1)
        try:
            return await run_in_threadpool(create_work, db, actor, metadata, data, key, request.state.correlation_id, file.filename or "")
        except (OSError, ValueError):
            raise storage_error() from None


@router.get("", response_model=LibraryPage)
def library(actor: Actor, db: Database, limit: Annotated[int, Query(ge=1, le=100)] = 20,
            after: uuid.UUID | None = None):
    query = select(Work).where(Work.owner_id == actor.owner_id, Work.deleted_at.is_(None))
    if after is not None:
        query = query.where(Work.id > after)
    works = list(db.scalars(query.order_by(Work.id).limit(limit + 1)))
    return LibraryPage(items=[work_view(db, work) for work in works[:limit]],
                       next_cursor=works[limit - 1].id if len(works) > limit else None)


@router.get("/{work_id}", response_model=WorkView)
def read_work(work_id: uuid.UUID, actor: Actor, db: Database, response: Response):
    found = work_view(db, owned_object(db, Work, work_id, actor))
    response.headers["ETag"] = f'"{found.revision}"'
    return found


@router.delete("/{work_id}", status_code=202, response_model=WorkDeletionView)
def delete_work(work_id: uuid.UUID, actor: Actor, db: Database, key: Key,
                match: Annotated[str | None, Header(alias="If-Match", max_length=32)] = None):
    return request_deletion(db, actor, work_id, match, key)


@router.get("/{work_id}/original")
def original(work_id: uuid.UUID, actor: Actor, db: Database):
    document = document_for(db, owned_object(db, Work, work_id, actor))
    try:
        data = PrivateSources().read(document.source_ref)
    except (OSError, ValueError):
        raise storage_error() from None
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="source.{document.format}"'})


@router.get("/{work_id}/chapters", response_model=ChapterPage)
def chapters(work_id: uuid.UUID, actor: Actor, db: Database,
             after: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 100):
    return list_chapters(db, actor, work_id, after, limit)


@router.get("/{work_id}/ingestions/{job_id}", response_model=IngestionView)
def read_ingestion(work_id: uuid.UUID, job_id: uuid.UUID, actor: Actor, db: Database, response: Response):
    document = document_for(db, owned_object(db, Work, work_id, actor))
    job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_id, IngestionJob.document_id == document.id))
    if job is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    response.headers["ETag"] = f'"{job.revision}"'
    return ingestion_view(job)


@router.post("/{work_id}/ingestions/{job_id}/{action}", response_model=IngestionView)
def change_ingestion(work_id: uuid.UUID, job_id: uuid.UUID, action: Literal["retry", "cancel"],
                     actor: Actor, db: Database, key: Key, response: Response,
                     match: Annotated[str | None, Header(alias="If-Match", max_length=32)] = None):
    view = mutate_job(db, actor, work_id, job_id, action, match, key)
    response.headers["ETag"] = f'"{view.revision}"'
    return view


@router.get("/{work_id}/generations", response_model=GenerationPage)
def generations(work_id: uuid.UUID, actor: Actor, db: Database):
    return list_generations(db, actor, work_id)


@router.post("/{work_id}/generations", status_code=202, response_model=GenerationView)
def rebuild(work_id: uuid.UUID, actor: Actor, db: Database, key: Key, request: Request):
    return create_generation(db, actor, work_id, key, request.state.correlation_id)
