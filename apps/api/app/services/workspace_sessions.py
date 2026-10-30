"""Private local workspace capabilities; receipt replays never choose an existing owner."""
import base64
import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

from app.core.errors import PublicError
from app.core.security import COOKIE_NAME, token_hash
from app.models.access import LoginSession, Principal, WorkspaceBootstrap
from app.schemas.access import PrincipalView
from sqlalchemy import select, text

LIFETIME = 90 * 24 * 60 * 60


def missing_access():
    return PublicError(401, "WORKSPACE_ACCESS_REQUIRED", "This workspace needs local access recovery.")


def bootstrap(db, request, response, key):
    secret = os.environ.get("VISION_WORKSPACE_SECRET", "")
    if len(secret) < 32:
        raise PublicError(503, "WORKSPACE_NOT_CONFIGURED", "Private workspace access is not configured.", True)
    now = datetime.now(UTC)
    cookie = request.cookies.get(COOKIE_NAME, "")
    if cookie:
        if len(cookie) != 43 or not cookie.isascii():
            raise missing_access()
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(cookie),
                            LoginSession.expires_at > now).with_for_update())
        if session is None:
            raise missing_access()
        principal = db.get(Principal, session.owner_id)
        token = cookie
    else:
        digest = hashlib.sha256(key.encode()).hexdigest()
        # Serialize duplicate first-visit receipts before either creates a principal.
        lock = int.from_bytes(bytes.fromhex(digest[:16]), "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        receipt = db.get(WorkspaceBootstrap, digest)
        token = base64.urlsafe_b64encode(hmac.digest(secret.encode(), b"vision-workspace-v1:" + key.encode(), "sha256")).decode().rstrip("=")
        if receipt is not None:
            session = db.get(LoginSession, token_hash(token))
            if receipt.replay_until <= now or session is None or session.expires_at <= now:
                raise missing_access()
            principal = db.get(Principal, receipt.owner_id)
            if principal is None or session.owner_id != principal.id:
                raise missing_access()
        else:
            principal = Principal(id=uuid.uuid4(), username="w_" + uuid.uuid4().hex[:30], password_hash="!")
            db.add(principal)
            db.flush()
            session = LoginSession(token_hash=token_hash(token), owner_id=principal.id,
                                   expires_at=now + timedelta(seconds=LIFETIME))
            db.add_all([session, WorkspaceBootstrap(key_hash=digest, owner_id=principal.id,
                                                   replay_until=now + timedelta(minutes=5))])
    session.expires_at = now + timedelta(seconds=LIFETIME)
    result = PrincipalView(id=principal.id, username=principal.username)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", secure=False, max_age=LIFETIME, path="/")
    return result


def issue_recovery(db, owner_id):
    """Local operator only; never exposed as an unauthenticated account lookup."""
    import secrets

    from app.models.access import WorkspaceRecovery
    from sqlalchemy import delete

    if db.get(Principal, owner_id) is None:
        raise missing_access()
    token = secrets.token_urlsafe(32)
    db.execute(delete(WorkspaceRecovery).where(WorkspaceRecovery.owner_id == owner_id))
    db.add(WorkspaceRecovery(key_hash=token_hash(token), owner_id=owner_id,
                             expires_at=datetime.now(UTC) + timedelta(minutes=15)))
    db.commit()
    return token


def recover(db, request, response, recovery_key, key):
    from app.models.access import WorkspaceRecovery

    secret = os.environ.get("VISION_WORKSPACE_SECRET", "")
    if len(secret) < 32:
        raise PublicError(503, "WORKSPACE_NOT_CONFIGURED", "Private workspace access is not configured.", True)
    now = datetime.now(UTC)
    receipt = db.scalar(select(WorkspaceRecovery).where(WorkspaceRecovery.key_hash == token_hash(recovery_key)).with_for_update())
    if receipt is None or receipt.expires_at <= now:
        raise missing_access()
    cookie = request.cookies.get(COOKIE_NAME, "")
    active = db.get(LoginSession, token_hash(cookie)) if cookie else None
    if active is not None and active.expires_at > now and active.owner_id != receipt.owner_id:
        raise PublicError(409, "WORKSPACE_CONFLICT", "Another private workspace is already open in this browser.")
    digest = token_hash(key)
    if receipt.used_key_hash is not None and receipt.used_key_hash != digest:
        raise missing_access()
    token = base64.urlsafe_b64encode(hmac.digest(secret.encode(), b"vision-recovery-v1:" + recovery_key.encode() + key.encode(), "sha256")).decode().rstrip("=")
    session = db.get(LoginSession, token_hash(token))
    if receipt.used_key_hash is not None and session is None:
        raise missing_access()
    if session is None:
        db.add(LoginSession(token_hash=token_hash(token), owner_id=receipt.owner_id,
                            expires_at=now + timedelta(seconds=LIFETIME)))
    receipt.used_key_hash = digest
    principal = db.get(Principal, receipt.owner_id)
    result = PrincipalView(id=principal.id, username=principal.username)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", secure=False, max_age=LIFETIME, path="/")
    return result
