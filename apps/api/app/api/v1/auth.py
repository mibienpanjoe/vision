import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from app.core.errors import PublicError
from app.core.http import BoundedJsonRoute
from app.core.passwords import verify_password
from app.core.security import (
    COOKIE_NAME,
    ActorScope,
    current_actor,
    database_session,
    require_origin,
    token_hash,
)
from app.models.access import LoginSession, Principal
from app.schemas.access import LoginRequest, PrincipalView
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/auth", tags=["identity"], route_class=BoundedJsonRoute)


@router.post("/login", response_model=PrincipalView)
def login(body: LoginRequest, request: Request, response: Response,
          db: Annotated[Session, Depends(database_session)]):
    require_origin(request)
    request.app.state.login_limiter.check()
    now = datetime.now(UTC)
    principal = db.scalar(select(Principal).where(Principal.username == body.username).with_for_update())
    if principal is not None and principal.locked_until and principal.locked_until > now:
        raise PublicError(401, "AUTHENTICATION_REQUIRED", "Invalid credentials.")
    if principal is not None and principal.locked_until:
        principal.failed_attempts, principal.locked_until = 0, None
    valid = verify_password(body.password, principal.password_hash if principal is not None else "")
    if principal is None or not valid:
        if principal is not None:
            principal.failed_attempts += 1
            if principal.failed_attempts >= 5:
                principal.locked_until = now + timedelta(minutes=5)
            db.commit()
        raise PublicError(401, "AUTHENTICATION_REQUIRED", "Invalid credentials.")
    principal.failed_attempts, principal.locked_until = 0, None
    previous = request.cookies.get(COOKIE_NAME, "")
    if len(previous) == 43 and previous.isascii():
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(previous)))
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(token), owner_id=principal.id, expires_at=now + timedelta(hours=12)))
    result = PrincipalView(id=principal.id, username=principal.username)
    db.commit()
    # Deliberately HTTP loopback only (DEC-25); no network deployment is supported.
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", secure=False, max_age=43200, path="/")
    return result


@router.get("/me", response_model=PrincipalView)
def me(actor: Annotated[ActorScope, Depends(current_actor)]):
    return PrincipalView(id=actor.owner_id, username=actor.username)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response,
           actor: Annotated[ActorScope, Depends(current_actor)],
           db: Annotated[Session, Depends(database_session)]):
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(request.cookies[COOKIE_NAME]),
                                          LoginSession.owner_id == actor.owner_id))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
