"""Compose a verified visual specification for an owned work; results are not stored yet (T32)."""

import uuid
from typing import Annotated

from app.core.security import ActorScope, current_actor, database_session
from app.schemas.retrieval import VisualizationRequest
from app.schemas.visualization import VisualizationResult
from app.services.visualization.specification import compose
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/works", tags=["visualization"])
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]


@router.post("/{work_id}/visualizations/compose", response_model=VisualizationResult)
def compose_visualization(work_id: uuid.UUID, body: VisualizationRequest, actor: Actor, db: Database,
                          request: Request):
    return VisualizationResult(compose(db, actor, work_id, body, request.state.correlation_id))
