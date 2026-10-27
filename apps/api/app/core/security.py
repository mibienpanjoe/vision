import hashlib
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from app.core.errors import PublicError
from app.core.storage import restore_marker
from app.models.access import LoginSession, Principal
from app.models.works import Work
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

COOKIE_NAME = "vision_session"


class LoginLimiter:
    """Bound unknown-account attempts too; one local API process, reset on restart. Each attempt reserves a slot
    before any password work, so concurrent bursts stay bounded; a successful sign-in returns its slot."""
    def __init__(self):
        self.attempts: deque[tuple[float, object]] = deque(maxlen=10)
        self.lock = threading.Lock()

    def check(self) -> object:
        now, slot = time.monotonic(), object()
        with self.lock:
            while self.attempts and self.attempts[0][0] <= now - 60:
                self.attempts.popleft()
            if len(self.attempts) == 10:
                raise PublicError(429, "RESOURCE_LIMIT", "Too many login attempts. Try again later.")
            self.attempts.append((now, slot))
        return slot

    def release(self, slot: object) -> None:
        with self.lock:
            self.attempts = deque((entry for entry in self.attempts if entry[1] is not slot), maxlen=10)


def require_origin(request: Request) -> None:
    allowed = os.environ.get("VISION_WEB_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
    if request.headers.get("origin") not in allowed:
        raise PublicError(403, "ORIGIN_REJECTED", "Request origin is not allowed.")


def database_session(request: Request):
    engine = request.app.state.engine
    if engine is None or restore_marker().exists():
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
    query = select(model).where(model.id == object_id, model.owner_id == actor.owner_id)
    # A work being deleted, and everything filed under it, is absent from the moment deletion is requested.
    if model is Work:
        query = query.where(Work.deleted_at.is_(None))
    elif hasattr(model, "work_id"):
        query = query.where(model.work_id.in_(select(Work.id).where(Work.deleted_at.is_(None))))
    result = db.scalar(query)
    if result is None:
        raise PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return result
