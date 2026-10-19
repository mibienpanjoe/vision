import hashlib
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import PublicError
from app.models.access import LoginSession, Principal

COOKIE_NAME = "vision_session"


class LoginLimiter:
    """Bound unknown-account attempts too; one local API process, reset on restart."""
    def __init__(self):
        self.attempts: deque[float] = deque(maxlen=10)
        self.lock = threading.Lock()

    def check(self):
        now = time.monotonic()
        with self.lock:
            while self.attempts and self.attempts[0] <= now - 60:
                self.attempts.popleft()
            if len(self.attempts) == 10:
                raise PublicError(429, "RESOURCE_LIMIT", "Too many login attempts. Try again later.")
            self.attempts.append(now)


def require_origin(request: Request) -> None:
    allowed = os.environ.get("VISION_WEB_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
    if request.headers.get("origin") not in allowed:
        raise PublicError(403, "ORIGIN_REJECTED", "Request origin is not allowed.")


def database_session(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise PublicError(503, "STORE_UNAVAILABLE", "Storage is unavailable.", True)
    with Session(engine) as db:
        yield db


@dataclass(frozen=True)
class ActorScope:
    owner_id: uuid.UUID
    username: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def current_actor(request: Request, db: Annotated[Session, Depends(database_session)]) -> ActorScope:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
    token = request.cookies.get(COOKIE_NAME, "")
    if len(token) == 43 and token.isascii():
        principal = db.scalar(select(Principal).join(LoginSession, LoginSession.owner_id == Principal.id).where(
            LoginSession.token_hash == token_hash(token), LoginSession.expires_at > datetime.now(UTC)))
        if principal is not None:
            return ActorScope(principal.id, principal.username)
    raise PublicError(401, "AUTHENTICATION_REQUIRED", "Authentication required.")


def owned_object(db: Session, model, object_id: uuid.UUID, actor: ActorScope):
    result = db.scalar(select(model).where(model.id == object_id, model.owner_id == actor.owner_id))
    if result is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return result
