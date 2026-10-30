"""Local operator only. Recovery URLs are written privately, never printed."""
import argparse
import os
from pathlib import Path

from app.db.session import configured_engine
from app.services.workspace_upgrade import upgrade_workspace
from local import ensure_workspace_secret


def main():
    root = Path(__file__).resolve().parents[1]
    env = root / ".env"
    parser = argparse.ArgumentParser(description="Back up, upgrade and recover one existing local workspace.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--recovery-file", required=True, type=Path)
    parser.add_argument("--web-port", type=int, default=3000)
    args = parser.parse_args()
    secret = ensure_workspace_secret(env)
    for line in env.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    os.environ.setdefault("VISION_WORKSPACE_SECRET", secret)
    engine = configured_engine()
    if engine is None:
        raise SystemExit("Local database configuration is required.")
    try:
        upgrade_workspace(engine, args.snapshot, args.recovery_file, args.username, args.web_port)
    finally:
        engine.dispose()
    print("Workspace preserved. Recovery link saved to the selected private file; never share or commit it.")


if __name__ == "__main__":
    main()
