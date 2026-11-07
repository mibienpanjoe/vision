"""Local-only developer commands; private configuration never enters output."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api"


def run(args, *, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def load_environment():
    path = ROOT / ".env"
    if not path.exists():
        raise SystemExit("Run make setup first.")
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def ensure_workspace_secret(path):
    lines = path.read_text().splitlines()
    current = next((line.split("=", 1)[1].strip() for line in lines if line.startswith("VISION_WORKSPACE_SECRET=")), "")
    if current:
        if len(current) < 32:
            raise SystemExit("VISION_WORKSPACE_SECRET must contain at least 32 random characters.")
        return current
    value = secrets.token_hex(32)
    lines = [line for line in lines if not line.startswith("VISION_WORKSPACE_SECRET=")]
    lines.append("VISION_WORKSPACE_SECRET=" + value)
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    return value


def setup():
    (ROOT / ".local").mkdir(exist_ok=True)
    required = {
        "node": ("--version", "v" + (ROOT / ".node-version").read_text().strip()),
        "pnpm": ("--version", "10.28.0"),
        "uv": ("--version", "uv 0.12.15"),
    }
    for tool, (flag, version) in required.items():
        actual = subprocess.check_output([tool, flag], text=True).strip()
        if actual != version and not actual.startswith(version + " "):
            raise SystemExit(f"Expected {tool} {version}; found {actual}")
    path = ROOT / ".env"
    if not path.exists():
        postgres, redis = secrets.token_hex(24), secrets.token_hex(24)
        pg_port, redis_port = (
            os.environ.get("POSTGRES_PORT", "55432"),
            os.environ.get("REDIS_PORT", "56379"),
        )
        contents = (
            f"POSTGRES_PASSWORD={postgres}\nPOSTGRES_PORT={pg_port}\n"
            f"DATABASE_URL=postgresql+psycopg://vision:{postgres}@127.0.0.1:{pg_port}/vision\n"
            f"REDIS_PASSWORD={redis}\nREDIS_PORT={redis_port}\n"
            f"REDIS_URL=redis://:{redis}@127.0.0.1:{redis_port}/0\n"
        )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(contents)
        print("Created private .env with local-only credentials.")
    else:
        print("Preserved existing private .env.")
    ensure_workspace_secret(path)
    run(["uv", "sync", "--project", "apps/api", "--locked"])
    models = ROOT / ".local/docling-models"
    if not models.is_dir():
        # One-time layout model fetch; the PDF worker itself never downloads.
        run(["uv", "run", "--locked", "docling-tools", "models", "download", "layout", "-o", str(models)], cwd=API)
    run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"])


def main():
    command = sys.argv[1]
    if command == "setup":
        setup()
        return
    load_environment()
    if command == "integration":
        os.environ["VISION_TEST_ADMIN_URL"] = os.environ["DATABASE_URL"]
        os.environ["VISION_TEST_REDIS_URL"] = os.environ["REDIS_URL"]
        run(
            [
                "uv",
                "run",
                "--project",
                "apps/api",
                "--locked",
                "pytest",
                "apps/api/tests",
                "-m",
                "integration",
                "-q",
            ]
        )
    elif command == "migrate":
        run(["uv", "run", "--locked", "alembic", "upgrade", "head"], cwd=API)
    elif command == "api":
        run(
            [
                "uv",
                "run",
                "--locked",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=API,
        )
    elif command == "reconcile-sources":
        run(["uv", "run", "--locked", "python", "-m", "app.services.ingestion.reconcile"], cwd=API)
    elif command in {"backup", "restore", "deletions"}:
        run(["uv", "run", "--locked", "python", "-m", "app.operations", command, *sys.argv[2:]], cwd=API)
    elif command in {"worker", "dispatch"}:
        run(["uv", "run", "--locked", "python", "-m", "app.workers.dispatch"], cwd=API)
        if command == "worker":
            run(
                [
                    "uv",
                    "run",
                    "--locked",
                    "dramatiq",
                    "app.workers.bootstrap",
                    "--processes",
                    "1",
                    "--threads",
                    "1",
                ],
                cwd=API,
            )
    elif command == "dev":
        processes = []
        try:
            for args, cwd in [
                (
                    [
                        "uv",
                        "run",
                        "--locked",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    API,
                ),
                ([sys.executable, str(ROOT / "scripts/local.py"), "worker"], ROOT),
                (["pnpm", "dev"], ROOT / "apps/web"),
            ]:
                processes.append(
                    subprocess.Popen(args, cwd=cwd, start_new_session=True)
                )
            while all(process.poll() is None for process in processes):
                time.sleep(0.5)
            raise SystemExit("A local service exited; stopping the workspace.")
        except KeyboardInterrupt:
            pass
        finally:
            import signal

            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in processes:
                process.wait(timeout=20)
    else:
        raise SystemExit("Unknown local command")


if __name__ == "__main__":
    main()
