"""Offline local backup/restore. Run on the host against the selected Compose database service."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.storage import REFERENCE, PrivateSources, private_renders, restore_marker
from app.db.session import configured_engine
from app.models.access import LoginSession, Principal
from app.models.embeddings import DIMENSION
from app.models.jobs import Job
from app.models.model_runs import Derivation
from app.models.narrative_jobs import NarrativeJob
from app.models.renders import RenderJob
from app.models.works import Document, IngestionJob, Work, WorkDeletion
from app.providers.embeddings import HashedEmbeddings, LocalEmbeddings
from app.services.ingestion.jobs import recover_ingestions
from app.services.narrative.pipeline import recover_narratives
from app.services.retrieval.semantic import index_version
from app.services.visualization.render import recover_renders, settle
from app.services.works.deletion import purge, stop_processing
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "docker-compose.yml").is_file()), None)


class SnapshotError(Exception):
    pass


def schema_head():
    return ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()


def pg_tool(engine, tool, *args, **io):
    if ROOT is None:
        raise SnapshotError("Run snapshot operations on the host checkout.")
    # Use the server image's matching client. No connection URL/password appears in argv or output.
    return subprocess.run(["docker", "compose", "exec", "-T", "db", tool, "-U", engine.url.username,
                           "-d", engine.url.database, *args], cwd=ROOT, check=True, stderr=subprocess.PIPE, **io)


def compose(*args, **io):
    if ROOT is None:
        raise SnapshotError("Run snapshot operations on the host checkout.")
    return subprocess.run(["docker", "compose", "--profile", "app", *args], cwd=ROOT, check=True,
                          capture_output=True, **io)


@contextmanager
def packaged_storage(restoring=False):
    """Stage stopped Compose volumes on the host; PostgreSQL's matching tools stay in the db container."""
    for service in ("api", "worker"):
        ids = compose("ps", "-a", "-q", service).stdout.decode().split()
        if service == "api" and not ids:
            raise SnapshotError("Create the target API container and volumes before restoring.")
        for container in ids:
            running = subprocess.check_output(["docker", "inspect", "-f", "{{.State.Running}}", container])
            if running.strip() == b"true":
                raise SnapshotError("Stop API and worker containers before snapshot operations.")
    previous = {key: os.environ.get(key) for key in ("VISION_SOURCE_ROOT", "VISION_RENDER_ROOT")}
    with tempfile.TemporaryDirectory(prefix="vision-snapshot-") as scratch:
        roots = {"originals": Path(scratch) / "originals", "renders": Path(scratch) / "renders"}
        try:
            for kind, root in roots.items():
                root.mkdir(mode=0o700)
                compose("cp", f"api:/data/{kind}/.", str(root))
                if restoring and any(root.iterdir()):
                    raise SnapshotError("Restore requires empty packaged storage volumes.")
            os.environ["VISION_SOURCE_ROOT"], os.environ["VISION_RENDER_ROOT"] = map(str, roots.values())
            if restoring:
                marker = Path(scratch) / ".restore-in-progress"
                private_write(marker, b"Packaged restore is incomplete.\n")
                compose("cp", str(marker), "api:/data/originals/.restore-in-progress")
            yield
            if restoring:
                expected = {}
                for kind, root in roots.items():
                    expected[kind] = {p.name: digest(p) for p in root.iterdir()}
                    compose("cp", str(root) + "/.", f"api:/data/{kind}")
                # docker cp creates root-owned files in a container. Repair only these new, private volumes,
                # verify every byte there, then remove the real volume's guard as the final publication.
                script = """
import hashlib, json, os, pathlib, sys
expected = json.load(sys.stdin)
for kind, files in expected.items():
    root = pathlib.Path('/data') / kind
    os.chown(root, 10001, 10001)
    os.chmod(root, 0o700)
    for path in root.iterdir():
        if path.name == '.restore-in-progress' and kind == 'originals':
            continue
        assert path.name in files and not path.is_symlink() and path.is_file()
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == files[path.name]
            os.chown(path, 10001, 10001)
            os.chmod(path, 0o600)
            os.fsync(stream.fileno())
    assert all((root / name).is_file() for name in files)
    descriptor = os.open(root, os.O_DIRECTORY)
    os.fsync(descriptor)
    os.close(descriptor)
marker = pathlib.Path('/data/originals/.restore-in-progress')
marker.unlink()
descriptor = os.open(marker.parent, os.O_DIRECTORY)
os.fsync(descriptor)
os.close(descriptor)
"""
                compose("run", "--rm", "--no-deps", "-T", "--user", "0", "--entrypoint", "python", "api", "-c", script,
                        input=json.dumps(expected).encode())
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def require_cluster(engine, connection):
    local = str(connection.scalar(text("SELECT system_identifier FROM pg_control_system()")))
    remote = pg_tool(engine, "psql", "-XAt", "-c", "SELECT system_identifier FROM pg_control_system()",
                     stdout=subprocess.PIPE).stdout.decode().strip()
    if local != remote:
        raise SnapshotError("Compose database does not match the selected database cluster.")


def private_write(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def digest(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_private(source, target):
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as incoming, target.open("xb") as outgoing:
        os.chmod(target, 0o600)
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    sync_directory(target.parent)


def ledger_data(connection):
    rows = connection.execute(select(WorkDeletion.__table__)).mappings()
    return {"format": 1, "exported_at": datetime.now(UTC).isoformat(),
            "deletions": [{k: str(v) if isinstance(v, (uuid.UUID, datetime)) else v for k, v in row.items()}
                          for row in rows]}


def export_deletions(engine, path):
    with engine.connect() as connection:
        data = ledger_data(connection)
    private_write(path, json.dumps(data).encode())


def backup(engine, directory):
    directory.mkdir(mode=0o700)  # Never overwrite an existing snapshot, including an interrupted one.
    objects = []
    with engine.connect() as connection, connection.begin():
        require_cluster(engine, connection)
        held = connection.scalar(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted "
                                      "AND database=(SELECT oid FROM pg_database WHERE datname=current_database())"))
        if held:
            raise SnapshotError("Stop the worker before taking a backup.")
        tables = inspect(connection).get_table_names()
        if "alembic_version" not in tables:
            raise SnapshotError("Source database is not initialized.")
        # Freeze SQL publication while copying immutable objects. A purge marks itself before unlinking files.
        names = ", ".join(connection.dialect.identifier_preparer.quote(t) for t in tables)
        connection.execute(text(f"LOCK TABLE {names} IN SHARE MODE"))
        if connection.scalar(text("SELECT count(*) FROM work_deletions WHERE status='purging'")):
            raise SnapshotError("Complete interrupted deletion before taking a backup.")
        schema = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if schema != schema_head():
            raise SnapshotError("Source schema does not match this release.")
        snapshot = connection.scalar(text("SELECT pg_export_snapshot()"))
        # https://www.postgresql.org/docs/17/app-pgdump.html (--snapshot, custom format)
        with (directory / "database.dump").open("xb") as output:
            os.chmod(directory / "database.dump", 0o600)
            pg_tool(engine, "pg_dump", "-Fc", "--no-owner", "--no-privileges", f"--snapshot={snapshot}", stdout=output)
            output.flush()
            os.fsync(output.fileno())
        stores = {"originals": PrivateSources(), "renders": private_renders()}
        references = {
            "originals": connection.execute(select(Document.source_ref, Document.sha256)).all(),
            "renders": connection.execute(select(RenderJob.output_reference, RenderJob.output_sha256).where(
                RenderJob.output_reference.is_not(None))).all(),
        }
        for kind, refs in references.items():
            (directory / kind).mkdir(mode=0o700)
            for reference, expected in dict(refs).items():
                destination = directory / kind / reference
                copy_private(stores[kind].path(reference), destination)
                if digest(destination) != expected:
                    raise SnapshotError("Source object integrity check failed.")
                objects.append({"kind": kind, "reference": reference, "sha256": expected})
        indexes = list(connection.scalars(select(Derivation.processing_version).where(
            Derivation.stage == "index", Derivation.status == "succeeded").distinct()))
        manifest = {"format": 1, "schema": schema, "created_at": datetime.now(UTC).isoformat(),
                    "dimension": DIMENSION, "indexes": indexes, "objects": objects,
                    "database_sha256": digest(directory / "database.dump")}
        private_write(directory / "deletions.json", json.dumps(ledger_data(connection)).encode())
        # Written last: a partial directory is never a usable backup.
        private_write(directory / "manifest.json", json.dumps(manifest).encode())
        sync_directory(directory.parent)
    return manifest


def validate(directory, ledger):
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise SnapshotError("Backup must be a private directory.")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest["format"] != 1 or manifest["schema"] != schema_head():
        raise SnapshotError("Backup schema is incompatible; use the matching release before migrating.")
    supported = {index_version(LocalEmbeddings()), index_version(HashedEmbeddings())}
    if manifest["dimension"] != DIMENSION or not set(manifest["indexes"]) <= supported:
        raise SnapshotError("Index version is incompatible; rebuild with the matching release before upgrading.")
    if digest(directory / "database.dump") != manifest["database_sha256"]:
        raise SnapshotError("Database backup integrity check failed.")
    for item in manifest["objects"]:
        if item["kind"] not in {"originals", "renders"} or not REFERENCE.fullmatch(item["reference"]):
            raise SnapshotError("Invalid object reference in backup.")
        if digest(directory / item["kind"] / item["reference"]) != item["sha256"]:
            raise SnapshotError("Object backup integrity check failed.")
    data = json.loads(ledger.read_bytes())
    if data["format"] != 1 or datetime.fromisoformat(data["exported_at"]) < datetime.fromisoformat(manifest["created_at"]):
        raise SnapshotError("Deletion ledger is older than the backup; export the latest ledger first.")
    return manifest, data


def require_empty(engine):
    with engine.connect() as connection:
        occupied = connection.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                          "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'"))
        if occupied:
            raise SnapshotError("Restore requires an empty target database.")
        require_cluster(engine, connection)


def restore(engine, directory, ledger):
    require_empty(engine)
    manifest, data = validate(directory, ledger)
    stores = {"originals": PrivateSources(), "renders": private_renders()}
    if any(any(store.root.iterdir()) for store in stores.values()):
        raise SnapshotError("Restore requires empty private storage roots.")
    private_write(restore_marker(), b"Restore is incomplete. Keep the target offline.\n")
    for item in manifest["objects"]:
        copy_private(directory / item["kind"] / item["reference"], stores[item["kind"]].path(item["reference"]))
    # https://www.postgresql.org/docs/17/app-pgrestore.html (--single-transaction implies --exit-on-error)
    with (directory / "database.dump").open("rb") as source:
        pg_tool(engine, "pg_restore", "--single-transaction", "--no-owner", "--no-privileges",
                stdin=source, stdout=subprocess.PIPE)
    with Session(engine) as db, db.begin():
        db.execute(delete(LoginSession))  # Never revive an old browser session.
        for row in data["deletions"]:
            owner_id, work_id = uuid.UUID(row["owner_id"]), uuid.UUID(row["work_id"])
            if db.get(Principal, owner_id) is None:
                continue  # Accounts created after the snapshot are outside its recovery point.
            existing = db.get(WorkDeletion, work_id)
            values = {**row, "owner_id": owner_id, "work_id": work_id, "dispatched_at": None}
            for key in ("requested_at", "completed_at"):
                values[key] = datetime.fromisoformat(values[key]) if values[key] else None
            if db.get(Work, work_id) is not None:
                values["status"], values["completed_at"] = "pending", None
                work = db.get(Work, work_id)
                work.deleted_at = values["requested_at"]
                stop_processing(db, work_id, values["requested_at"])
            if existing is None:
                db.add(WorkDeletion(**values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
        db.execute(update(IngestionJob).where(IngestionJob.status == "queued").values(dispatched_at=None))
        db.execute(update(Job).where(Job.status == "queued").values(dispatched_at=None))
        db.execute(update(NarrativeJob).where(NarrativeJob.status == "queued").values(dispatched_at=None))
        # A queued snapshot may predate a charged call on the old instance. Without its later receipt,
        # even "queued" is uncertain after restoration; never automatically publish it again.
        for job in db.scalars(select(RenderJob).where(RenderJob.status == "queued")):
            settle(job, "acceptance_unknown", "RENDER_RESTORED")
    recover_ingestions(engine)
    recover_narratives(engine)
    recover_renders(engine)  # Claimed images settle unknown; recovery never calls a provider.
    with Session(engine) as db:
        deletions = list(db.scalars(select(WorkDeletion.work_id).where(WorkDeletion.status != "completed")))
    for work_id in deletions:
        purge(engine, work_id)
    # Validate the surviving authoritative references after replaying deletions.
    with Session(engine) as db:
        for reference, expected in db.execute(select(Document.source_ref, Document.sha256)):
            if digest(stores["originals"].path(reference)) != expected:
                raise SnapshotError("Restored source integrity check failed.")
        for reference, expected in db.execute(select(RenderJob.output_reference, RenderJob.output_sha256).where(
                RenderJob.output_reference.is_not(None))):
            if digest(stores["renders"].path(reference)) != expected:
                raise SnapshotError("Restored image integrity check failed.")
    restore_marker().unlink()
    sync_directory(stores["originals"].root)
    for store in stores.values():
        sync_directory(store.root.parent)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Offline local snapshots; stop API/worker first. Restore into a new target.")
    parser.add_argument("command", choices=["backup", "deletions", "restore"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--deletions", type=Path, help="Latest exported deletion ledger, required for restore")
    parser.add_argument("--packaged", action="store_true", help="Use stopped Compose API storage volumes")
    args = parser.parse_args()
    if args.command == "restore" and args.deletions is None:
        parser.error("restore requires --deletions with the latest exported ledger")
    engine = configured_engine()
    if engine is None:
        parser.error("Configure DATABASE_URL first")
    try:
        if args.command == "deletions":
            export_deletions(engine, args.path)
        else:
            if args.command == "restore":
                require_empty(engine)
                validate(args.path, args.deletions)
            if args.packaged:
                with packaged_storage(restoring=args.command == "restore"):
                    if args.command == "backup":
                        backup(engine, args.path)
                    else:
                        restore(engine, args.path, args.deletions)
            elif args.command == "backup":
                backup(engine, args.path)
            else:
                restore(engine, args.path, args.deletions)
        print(f"{args.command} completed. Keep the target offline until acceptance; use a fresh Redis namespace.")
    except SnapshotError as error:
        parser.exit(1, f"{error}\n")
    except (OSError, ValueError, KeyError, SQLAlchemyError, subprocess.CalledProcessError):
        parser.exit(1, "Snapshot operation failed; keep the target offline. No connection or source details are logged.\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
