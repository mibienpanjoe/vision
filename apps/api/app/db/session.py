"""Database connection boundary; no global connection on import."""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def configured_engine() -> Engine | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
        hide_parameters=True,
    )
