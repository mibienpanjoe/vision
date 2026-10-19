from app.db.session import configured_engine
from app.services.dispatch import dispatch_pending


def main() -> None:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("Configure DATABASE_URL before dispatch")
    try:
        total = 0
        while count := dispatch_pending(engine):
            total += count
        print(f"Published {total} pending job(s).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
