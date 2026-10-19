import os

from alembic import context

from app.db.session import configured_engine

if context.is_offline_mode():
    context.configure(url=os.environ["DATABASE_URL"], literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = configured_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL must be configured before migrations")
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
