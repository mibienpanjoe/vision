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
library = os.environ.get("VISION_TEST_LIBRARY") == "1"
url = make_url(os.environ.get("DATABASE_URL", values["DATABASE_URL"]))
name = "vision_test_" + uuid.uuid4().hex
with socket.socket() as port_probe:
    port_probe.bind(("127.0.0.1", 8000))
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
        "VISION_WEB_ORIGINS": "http://127.0.0.1:13000",
        "VISION_SOURCE_ROOT": str(Path(source_directory.name) / "originals"),
        "REDIS_URL": values["REDIS_URL"],
        "VISION_QUEUE_NAMESPACE": name,
        "VISION_NARRATIVE_PROVIDER": "off",
        "VISION_TEST_PARSE_GATE": str(Path(source_directory.name) / "parse-gate"),
    }
    os.environ["DATABASE_URL"] = test_url
    command.upgrade(Config(str(root / "apps/api/alembic.ini")), "head")
    if library:
        subprocess.run(
            [str(root / "apps/api/.venv/bin/python"), "-m", "app.cli", "create-user", "other_reader", "--password-stdin"],
            input="synthetic session transport passphrase\n", text=True, cwd=root / "apps/api", env=env, check=True,
        )
        worker_log = (root / ".local/library-worker.log").open("w")
        worker = subprocess.Popen(
            [str(root / "apps/api/.venv/bin/dramatiq"), "tests.browser_worker", "--processes", "1", "--threads", "1", "--queues", "ingestion"],
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
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=root / "apps/api",
        env=env,
        stdout=log,
        stderr=log,
    )
    for _ in range(80):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/health/ready", timeout=1
            ) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Isolated API did not become ready")
    subprocess.run(
        ["pnpm", "--dir", "apps/web", "test", "tests/library.spec.ts" if library else "tests/session.spec.ts", "--workers=1"],
        env={**env, "VISION_TEST_WEB_SESSION": "1"},
        check=True,
    )
    if library:
        fixture_db = create_engine(test_url)
        try:
            with fixture_db.connect() as db:
                status, passages = db.execute(text(
                    "SELECT j.status, (SELECT count(*) FROM passages p WHERE p.document_id = d.id) "
                    "FROM works w JOIN documents d ON d.work_id = w.id "
                    "JOIN ingestion_jobs j ON j.document_id = d.id WHERE w.title = :title"
                ), {"title": "Slow parsing"}).one()
                assert (status, passages) == ("cancelled", 0)
                print("Running cancellation persisted: cancelled, zero published passages.")
        finally:
            fixture_db.dispose()
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
