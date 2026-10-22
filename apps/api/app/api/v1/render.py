import uuid
from typing import Annotated

from app.core.http import BoundedJsonRoute
from app.core.security import ActorScope, current_actor, database_session
from app.schemas.render import RenderCancel, RenderCreate, RenderView
from app.services.visualization import render
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/works", tags=["render"], route_class=BoundedJsonRoute)
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


@router.post("/{work_id}/visualizations/{visualization_id}/renders", response_model=RenderView, status_code=202)
def create_render(work_id: uuid.UUID, visualization_id: uuid.UUID, body: RenderCreate,
                  actor: Actor, db: Database, key: Key, response: Response):
    found = render.reserve(db, actor, work_id, visualization_id, body, key)
    response.headers["ETag"] = f'"{found.revision}"'
    return found


@router.get("/{work_id}/renders/{job_id}", response_model=RenderView)
def read_render(work_id: uuid.UUID, job_id: uuid.UUID, actor: Actor, db: Database, response: Response):
    found = RenderView.from_job(render.owned(db, actor, work_id, job_id))
    response.headers["ETag"] = f'"{found.revision}"'
    return found


@router.post("/{work_id}/renders/{job_id}/cancel", response_model=RenderView)
def cancel_render(work_id: uuid.UUID, job_id: uuid.UUID, body: RenderCancel, actor: Actor, db: Database,
                  key: Key, response: Response,
                  match: Annotated[str | None, Header(alias="If-Match", max_length=32)] = None):
    found = render.cancel(db, actor, work_id, job_id, match, key)
    response.headers["ETag"] = f'"{found.revision}"'
    return found
