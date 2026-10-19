import asyncio
import uuid
from typing import Annotated

from app.core.security import ActorScope, current_actor, database_session
from app.schemas.evidence import EvidenceRequest, EvidenceView
from app.services.verification.provenance import resolve_evidence
from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException


class BoundedEvidenceRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            received = 0

            async def receive():
                nonlocal received
                message = await request.receive()
                received += len(message.get("body", b""))
                if received > 32768:
                    raise HTTPException(413)
                return message

            try:
                async with asyncio.timeout(10):
                    return await original(Request(request.scope, receive))
            except TimeoutError:
                raise HTTPException(408) from None

        return handler


router = APIRouter(prefix="/v1/works", tags=["evidence"], route_class=BoundedEvidenceRoute)


@router.post("/{work_id}/evidence", response_model=EvidenceView)
def evidence(work_id: uuid.UUID, body: EvidenceRequest,
             actor: Annotated[ActorScope, Depends(current_actor)],
             db: Annotated[Session, Depends(database_session)]):
    return resolve_evidence(db, actor, work_id, body)
