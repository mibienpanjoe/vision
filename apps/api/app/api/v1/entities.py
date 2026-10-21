import uuid
from typing import Annotated

from app.core.security import ActorScope, current_actor, database_session
from app.schemas.entities import EntityDetail, EntityPage
from app.services.narrative.browse import entity_detail, list_entities
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/works", tags=["narrative"])
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]
Cutoff = Annotated[uuid.UUID | None, Query(description="Reading cutoff chapter; omit for the whole book")]


@router.get("/{work_id}/entities", response_model=EntityPage)
def entities(work_id: uuid.UUID, actor: Actor, db: Database, through_chapter_id: Cutoff = None):
    return list_entities(db, actor, work_id, through_chapter_id)


@router.get("/{work_id}/entities/{entity_id}", response_model=EntityDetail)
def entity(work_id: uuid.UUID, entity_id: uuid.UUID, actor: Actor, db: Database, through_chapter_id: Cutoff = None):
    return entity_detail(db, actor, work_id, entity_id, through_chapter_id)
