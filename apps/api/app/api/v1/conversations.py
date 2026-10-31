"""Owner-scoped conversation resources; execution is a separately dispatched turn."""
import uuid
from typing import Annotated

from app.core.http import BoundedJsonRoute
from app.core.security import ActorScope, current_actor, database_session
from app.schemas.conversations import (
    ConversationCreate,
    ConversationMessagePage,
    ConversationPage,
    ConversationView,
    PromptCardView,
    TurnView,
)
from app.services.conversations import resources, store
from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/conversations", tags=["conversations"], route_class=BoundedJsonRoute)
Actor = Annotated[ActorScope, Depends(current_actor)]
Database = Annotated[Session, Depends(database_session)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
Limit = Annotated[int, Query(ge=1, le=50)]


@router.post("", response_model=ConversationView, status_code=201)
def create_conversation(body: ConversationCreate, actor: Actor, db: Database, key: Key, response: Response):
    thread = store.create(db, actor, body.work_id, body.title, key)
    db.commit()
    response.headers["ETag"] = f'"{thread.revision}"'
    return resources.view(db, actor, thread)


@router.get("", response_model=ConversationPage)
def list_conversations(actor: Actor, db: Database, after: uuid.UUID | None = None, limit: Limit = 30, work_id: uuid.UUID | None = None):
    return resources.page(db, actor, after, limit, work_id)


@router.get("/{conversation_id}", response_model=ConversationView)
def read_conversation(conversation_id: uuid.UUID, actor: Actor, db: Database, response: Response):
    thread = store.owned(db, actor, conversation_id)
    response.headers["ETag"] = f'"{thread.revision}"'
    return resources.view(db, actor, thread)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagePage)
def list_messages(conversation_id: uuid.UUID, actor: Actor, db: Database,
                  after: Annotated[int, Query(ge=0)] = 0, limit: Limit = 30):
    return resources.messages(db, actor, conversation_id, after, limit)


@router.get("/{conversation_id}/turns/{turn_id}", response_model=TurnView)
def read_turn(conversation_id: uuid.UUID, turn_id: uuid.UUID, actor: Actor, db: Database):
    return resources.turn(db, actor, conversation_id, turn_id)


@router.get("/{conversation_id}/cards/{number}", response_model=PromptCardView)
def read_card(conversation_id: uuid.UUID, number: int, actor: Actor, db: Database):
    return resources.card(db, actor, store.owned(db, actor, conversation_id), number)
