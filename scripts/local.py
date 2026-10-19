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
    run(["uv", "sync", "--project", "apps/api", "--locked"])
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
