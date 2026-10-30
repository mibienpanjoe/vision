"""Trusted local upgrade: snapshot first, preserve identity, then issue one-time recovery."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.models.access import Principal
from app.models.works import Document, Work
from app.operations import SnapshotError, backup, private_write
from app.services.workspace_sessions import issue_recovery
from sqlalchemy import select, text
from sqlalchemy.orm import Session


def fingerprint(db, owner_id):
    principal = db.get(Principal, owner_id)
    works = list(db.execute(select(Work.id, Document.id, Document.sha256, Document.current_generation_id)
                           .join(Document, Document.work_id == Work.id).where(Work.owner_id == owner_id)))
    return principal.render_reservations_used, sorted(tuple(map(str, row)) for row in works)


def upgrade_workspace(engine, archive: Path, recovery_file: Path, username: str, port=3000):
    if len(os.environ.get("VISION_WORKSPACE_SECRET", "")) < 32:
        raise SnapshotError("Configure a private workspace signing secret before upgrade.")
    if recovery_file.exists() or recovery_file.is_symlink() or not 1 <= port <= 65535:
        raise SnapshotError("Use a new private recovery file and a valid loopback port.")
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    with Session(engine) as db:
        principal = db.scalar(select(Principal).where(Principal.username == username))
        if principal is None:
            raise SnapshotError("Selected local workspace does not exist.")
        owner_id, before = principal.id, fingerprint(db, principal.id)
        schema = db.scalar(text("SELECT version_num FROM alembic_version"))
    if schema < "0026" or scripts.get_revision(schema) is None:
        raise SnapshotError("This local workspace needs its earlier release upgrade first.")
    list(scripts.iterate_revisions("head", schema))  # Validate a forward path before taking the snapshot.
    backup(engine, archive, source_schema=schema)
    previous = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
    with Session(engine) as db:
        if fingerprint(db, owner_id) != before:
            raise SnapshotError("Workspace identity changed; preserve the snapshot for local recovery.")
        token = issue_recovery(db, owner_id)
    recovery_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_write(recovery_file, f"http://127.0.0.1:{port}/#recover={token}\n".encode())
    return owner_id
