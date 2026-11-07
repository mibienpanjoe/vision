import os
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text().splitlines()
    if line and not line.startswith("#")
)
# Billed: the workspace harness with the configured image provider instead of the synthetic one.
conversation = os.environ.get("VISION_TEST_CONVERSATION") == "1"
workspace = os.environ.get("VISION_TEST_WORKSPACE") == "1" or conversation
api_port = int(os.environ.get("VISION_TEST_API_PORT", "8000"))
url = make_url(os.environ.get("DATABASE_URL", values["DATABASE_URL"]))
name = "vision_test_" + uuid.uuid4().hex
with socket.socket() as port_probe:
    port_probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    port_probe.bind(("127.0.0.1", api_port))
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as db:
    db.execute(text(f'CREATE DATABASE "{name}"'))
test_url = url.set(database=name).render_as_string(hide_password=False)
api = None
worker = None
worker_log = None
log = None
source_directory = tempfile.TemporaryDirectory(prefix="vision-session-")
try:
    env = {
        **os.environ,
        "DATABASE_URL": test_url,
        "VISION_WORKSPACE_SECRET": "synthetic-workspace-signing-secret-for-isolated-tests-only",
        "VISION_WEB_ORIGINS": "http://127.0.0.1:13000",
        "VISION_SOURCE_ROOT": str(Path(source_directory.name) / "originals"),
        "VISION_RENDER_ROOT": str(Path(source_directory.name) / "renders"),
        "REDIS_URL": values["REDIS_URL"],
        "VISION_QUEUE_NAMESPACE": name,
        "VISION_NARRATIVE_PROVIDER": "local" if workspace else "off",
        "VISION_TEST_WORKSPACE": "1" if workspace else "0",
        "VISION_TEST_PARSE_GATE": str(Path(source_directory.name) / "parse-gate"),
    }
    if conversation:
        # Reservations need a selected provider; the worker swaps in synthetic images, and the token is fake.
        env.update(VISION_RENDER_PROVIDER="huggingface", HF_TOKEN="synthetic-unused-token", VISION_RENDER_MODEL="")
    os.environ["DATABASE_URL"] = test_url
    command.upgrade(Config(str(root / "apps/api/alembic.ini")), "head")
    if workspace:
        subprocess.run(
            [str(root / "apps/api/.venv/bin/python"), "-m", "app.cli", "create-user", "other_reader", "--password-stdin"],
            input="synthetic session transport passphrase\n", text=True, cwd=root / "apps/api", env=env, check=True,
        )
        worker_log = (root / ".local/session-worker.log").open("w")
        worker = subprocess.Popen(
            [str(root / "apps/api/.venv/bin/dramatiq"), "tests.conversation_upload_worker" if conversation else "tests.browser_worker", "--processes", "1", "--threads", "2" if conversation else "1", "--queues", "ingestion", "retention", *( ["narrative", "render"] if workspace else [] ), *( ["conversation"] if conversation else [] )],
            cwd=root / "apps/api", env=env, stdout=worker_log, stderr=worker_log, start_new_session=True,
        )
        env["VISION_TEST_WORKER_PID"] = str(worker.pid)
    subprocess.run(
        [
            str(root / "apps/api/.venv/bin/python"),
            "-m",
            "app.cli",
            "create-user",
            "transport_reader",
            "--password-stdin",
        ],
        input="synthetic session transport passphrase\n",
        text=True,
        cwd=root / "apps/api",
        env=env,
        check=True,
    )
    log = (root / ".local/session-api.log").open("w")
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "--locked",
            "uvicorn",
            "tests.browser_app:app" if workspace else "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=root / "apps/api",
        env=env,
        stdout=log,
        stderr=log,
    )
    for _ in range(80):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{api_port}/health/ready", timeout=1
            ) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Isolated API did not become ready")
    if conversation:
        specs = os.environ.get("VISION_TEST_CONVERSATION_SPECS", "tests/conversation-upload.spec.ts tests/conversation-prompt.spec.ts tests/conversation-moments.spec.ts tests/conversation-sources.spec.ts tests/conversation-images.spec.ts tests/conversation-resume.spec.ts tests/conversation-recovery.spec.ts tests/conversation-flow.spec.ts").split()
    elif workspace:
        specs = os.environ.get(
            "VISION_TEST_WORKSPACE_SPECS",
            "tests/security.spec.ts",
        ).split()
    else:
        specs = os.environ.get("VISION_TEST_SESSION_SPECS", "tests/session.spec.ts tests/workspace-session.spec.ts").split()
    subprocess.run(
        ["pnpm", "--dir", "apps/web", "test", *specs, "--workers=1"],
        env={**env, "VISION_TEST_WEB_SESSION": "1"},
        check=True,
    )
finally:
    if worker is not None:
        os.killpg(worker.pid, signal.SIGCONT)
        worker.terminate()
        worker.wait(timeout=20)
    if worker_log is not None:
        worker_log.close()
    if api is not None:
        api.terminate()
        api.wait(timeout=10)
    if log is not None:
        log.close()
    with admin.connect() as db:
        db.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name"
            ),
            {"name": name},
        )
        db.execute(text(f'DROP DATABASE "{name}"'))
    admin.dispose()
    from redis import Redis

    broker = Redis.from_url(values["REDIS_URL"])
    keys = list(broker.scan_iter(match=name + ":*"))
    if keys:
        broker.delete(*keys)
    broker.close()
    source_directory.cleanup()
# Telemetry names IDs, codes and durations, never private text or credentials (SECURITY.md).
for path in (root / ".local/session-api.log", root / ".local/session-worker.log"):
    if path.exists():
        logged = path.read_text(errors="replace")
        for private in ("synthetic session transport passphrase", "Before dinner, Arthur removed", "SYSTEM OVERRIDE"):
            assert private not in logged, f"{path.name} contains private text"
print("API and worker logs carry no source text or passwords.")
