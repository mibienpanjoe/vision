"""Setup preserves a valid signing secret and repairs an empty template value."""
import runpy
from pathlib import Path

import pytest


def test_workspace_secret_is_private_and_stable(tmp_path):
    ensure = runpy.run_path(str(Path(__file__).parents[3] / "scripts/local.py"))["ensure_workspace_secret"]
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=untouched\nVISION_WORKSPACE_SECRET=\n")
    value = ensure(env)
    assert len(value) == 64 and ensure(env) == value
    assert env.read_text().startswith("DATABASE_URL=untouched\n")
    assert env.stat().st_mode & 0o777 == 0o600
    env.write_text("VISION_WORKSPACE_SECRET=invalid\n")
    with pytest.raises(SystemExit):
        ensure(env)
