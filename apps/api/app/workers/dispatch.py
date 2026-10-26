from app.db.session import configured_engine
from app.services.dispatch import (
    dispatch_deletions,
    dispatch_ingestions,
    dispatch_narratives,
    dispatch_pending,
    dispatch_renders,
)
from app.services.ingestion.jobs import recover_ingestions
from app.services.narrative.pipeline import recover_narratives
from app.services.visualization.render import recover_renders
from app.services.works.deletion import recover_deletions


def main() -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Configure DATABASE_URL before dispatch")
    try:
        recovered = recover_ingestions(engine)
        print(f"Reconciled {recovered} interrupted ingestion job(s).")
        print(f"Reconciled {recover_narratives(engine)} interrupted narrative job(s).")
        print(f"Settled {recover_renders(engine)} interrupted render job(s) as acceptance unknown.")
        print(f"Reconciled {recover_deletions(engine)} unfinished deletion(s).")
        total = 0
        while count := dispatch_pending(engine):
            total += count
        while count := dispatch_ingestions(engine):
            total += count
        while count := dispatch_narratives(engine):
            total += count
        while count := dispatch_renders(engine):
            total += count
        while count := dispatch_deletions(engine):
            total += count
        print(f"Published {total} pending job(s).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
