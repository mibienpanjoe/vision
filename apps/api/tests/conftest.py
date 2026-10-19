"""Explicitly opted-in PostgreSQL tests, isolated from the reader's database."""
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("VISION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set VISION_TEST_ADMIN_URL to opt into isolated PostgreSQL tests")
    name = "vision_test_" + uuid.uuid4().hex
    admin = create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = make_url(url).set(database=name)
    monkeypatch.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
    engine = create_engine(test_url)
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                    "WHERE datname = :name AND pid <> pg_backend_pid()"), {"name": name})
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()

