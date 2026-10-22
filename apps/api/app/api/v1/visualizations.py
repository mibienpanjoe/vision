"""Compose, store and read verified visual specifications of an owned work."""

import uuid
from typing import Annotated

from app.core.http import BoundedJsonRoute
from app.core.security import ActorScope, current_actor, database_session
from app.schemas.retrieval import VisualizationRequest
from app.schemas.visualization import (
    RefinementRequest,
    RevisionPage,
    VisualizationCreated,
    VisualizationPage,
    VisualizationResult,
    VisualizationView,
)
from app.services.visualization import history
from app.services.visualization.refinement import refine
from app.services.visualization.specification import compose
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/works", tags=["visualization"])
mutations = APIRouter(route_class=BoundedJsonRoute)
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


@router.post("/{work_id}/visualizations/compose", response_model=VisualizationResult)
def compose_visualization(work_id: uuid.UUID, body: VisualizationRequest, actor: Actor, db: Database,
                          request: Request):
    return VisualizationResult(compose(db, actor, work_id, body, request.state.correlation_id))


@router.post("/{work_id}/visualizations", response_model=VisualizationCreated, status_code=201)
def create_visualization(work_id: uuid.UUID, body: VisualizationRequest, actor: Actor, db: Database, key: Key,
                         request: Request, response: Response):
    status, created = history.create(db, actor, work_id, body, key, request.state.correlation_id)
    response.status_code = status
    if created.visualization is not None:
        response.headers["ETag"] = f'"{created.visualization.revision}"'
    return created


@router.get("/{work_id}/visualizations", response_model=VisualizationPage)
def list_visualizations(work_id: uuid.UUID, actor: Actor, db: Database,
                        generation_id: uuid.UUID | None = None, through_chapter_id: uuid.UUID | None = None):
    scope = history.read_scope(db, actor, work_id, generation_id, through_chapter_id)
    return history.list_visualizations(db, actor, work_id, scope)


@router.get("/{work_id}/visualizations/{visualization_id}", response_model=VisualizationView)
def read_visualization(work_id: uuid.UUID, visualization_id: uuid.UUID, actor: Actor, db: Database,
                       response: Response, generation_id: uuid.UUID | None = None, through_chapter_id: uuid.UUID | None = None):
    scope = history.read_scope(db, actor, work_id, generation_id, through_chapter_id)
    found = history.view(db, history.owned(db, actor, work_id, visualization_id), scope=scope)
    response.headers["ETag"] = f'"{found.revision}"'
    return found


@router.get("/{work_id}/visualizations/{visualization_id}/revisions", response_model=RevisionPage)
def list_revisions(work_id: uuid.UUID, visualization_id: uuid.UUID, actor: Actor, db: Database,
                   generation_id: uuid.UUID | None = None, through_chapter_id: uuid.UUID | None = None):
    scope = history.read_scope(db, actor, work_id, generation_id, through_chapter_id)
    return history.revisions(db, actor, work_id, visualization_id, scope)


@router.get("/{work_id}/visualizations/{visualization_id}/revisions/{number}", response_model=VisualizationView)
def read_revision(work_id: uuid.UUID, visualization_id: uuid.UUID, number: int, actor: Actor, db: Database,
                   generation_id: uuid.UUID | None = None, through_chapter_id: uuid.UUID | None = None):
    scope = history.read_scope(db, actor, work_id, generation_id, through_chapter_id)
    return history.view(db, history.owned(db, actor, work_id, visualization_id), number, scope)


@mutations.post("/{work_id}/visualizations/{visualization_id}/refinements", response_model=VisualizationView)
def refine_visualization(work_id: uuid.UUID, visualization_id: uuid.UUID, body: RefinementRequest,
                         actor: Actor, db: Database, key: Key, response: Response,
                         match: Annotated[str | None, Header(alias="If-Match", max_length=32)] = None):
    found = refine(db, actor, work_id, visualization_id, body, match, key)
    response.headers["ETag"] = f'"{found.revision}"'
    return found


router.include_router(mutations)
