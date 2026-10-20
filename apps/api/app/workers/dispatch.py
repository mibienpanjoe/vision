from app.db.session import configured_engine
from app.services.dispatch import dispatch_ingestions, dispatch_pending
from app.services.ingestion.jobs import recover_ingestions


def main() -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Configure DATABASE_URL before dispatch")
    try:
        recovered = recover_ingestions(engine)
        print(f"Reconciled {recovered} interrupted ingestion job(s).")
        total = 0
        while count := dispatch_pending(engine):
            total += count
        while count := dispatch_ingestions(engine):
            total += count
        print(f"Published {total} pending job(s).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
