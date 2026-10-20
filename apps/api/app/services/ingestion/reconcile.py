"""Remove only old, unreferenced, unlocked originals; leave uncertain state alone."""

import fcntl
import os
import time

from app.core.storage import REFERENCE, PrivateSources
from app.db.session import configured_engine
from app.models.works import Document
from sqlalchemy import select
from sqlalchemy.orm import Session


def reconcile_originals(engine, store: PrivateSources, minimum_age: int = 3600) -> int:
    removed = 0
    for path in store.root.iterdir():
        if not REFERENCE.fullmatch(path.name):
            continue
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except (FileNotFoundError, OSError):
            continue
        with os.fdopen(descriptor, "rb") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            if os.fstat(stream.fileno()).st_mtime > time.time() - minimum_age:
                continue
            with Session(engine) as db:
                if db.scalar(select(Document.id).where(Document.source_ref == path.name)) is not None:
                    continue
                path.unlink()
                removed += 1
    return removed


if __name__ == "__main__":
    engine = configured_engine()
    if engine is None:
        raise SystemExit("Configure DATABASE_URL before reconciliation")
    try:
        print(f"Removed {reconcile_originals(engine, PrivateSources())} interrupted originals.")
    finally:
        engine.dispose()
