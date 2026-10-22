import uuid
from typing import Annotated

from app.core.http import BoundedJsonRoute
from app.core.security import ActorScope, current_actor, database_session
from app.schemas.evidence import EvidenceRequest, EvidenceView
from app.services.verification.provenance import resolve_evidence
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/works", tags=["evidence"], route_class=BoundedJsonRoute)


@router.post("/{work_id}/evidence", response_model=EvidenceView)
def evidence(work_id: uuid.UUID, body: EvidenceRequest,
             actor: Annotated[ActorScope, Depends(current_actor)],
             db: Annotated[Session, Depends(database_session)]):
    return resolve_evidence(db, actor, work_id, body)
