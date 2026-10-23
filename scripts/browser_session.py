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
# Billed: the workspace harness with the configured image provider instead of the synthetic one.
live_render = os.environ.get("VISION_TEST_LIVE_RENDER") == "1"
live = os.environ.get("VISION_TEST_LIVE_WORKSPACE") == "1"
workspace = os.environ.get("VISION_TEST_WORKSPACE") == "1" or live or live_render
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
        **(values if live else {}),
        **os.environ,
        "DATABASE_URL": test_url,
        "VISION_WEB_ORIGINS": "http://127.0.0.1:13000",
        "VISION_SOURCE_ROOT": str(Path(source_directory.name) / "originals"),
        "VISION_RENDER_ROOT": str(Path(source_directory.name) / "renders"),
        "REDIS_URL": values["REDIS_URL"],
        "VISION_QUEUE_NAMESPACE": name,
        "VISION_NARRATIVE_PROVIDER": "local" if workspace else "off",
        "VISION_TEST_PARSE_GATE": str(Path(source_directory.name) / "parse-gate"),
    }
    if live:
        env["HF_HUB_OFFLINE"] = "1"
    os.environ["DATABASE_URL"] = test_url
    command.upgrade(Config(str(root / "apps/api/alembic.ini")), "head")
    if library or workspace:
        subprocess.run(
            [str(root / "apps/api/.venv/bin/python"), "-m", "app.cli", "create-user", "other_reader", "--password-stdin"],
            input="synthetic session transport passphrase\n", text=True, cwd=root / "apps/api", env=env, check=True,
        )
        worker_log = (root / ".local/library-worker.log").open("w")
        worker = subprocess.Popen(
            [str(root / "apps/api/.venv/bin/dramatiq"), "app.workers.bootstrap" if live else "tests.browser_worker", "--processes", "1", "--threads", "1", "--queues", "ingestion", *( ["narrative", "render"] if workspace else [] )],
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
            "tests.browser_app:app" if workspace and not live else "app.main:app",
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
    if live:
        specs = ["tests/product-flow.spec.ts"]
    elif live_render:
        specs = ["tests/render-flow.spec.ts"]
    elif workspace:
        specs = os.environ.get(
            "VISION_TEST_WORKSPACE_SPECS",
            "tests/accessibility.spec.ts tests/explorer.spec.ts tests/evidence.spec.ts "
            "tests/visualization.spec.ts tests/refinement.spec.ts tests/render-history.spec.ts tests/security.spec.ts",
        ).split()
    else:
        specs = ["tests/library.spec.ts" if library else "tests/session.spec.ts"]
    subprocess.run(
        ["pnpm", "--dir", "apps/web", "test", *specs, "--workers=1"],
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
    if live:
        fixture_db = create_engine(test_url)
        try:
            with fixture_db.connect() as db:
                providers = set(db.scalars(text("SELECT DISTINCT provider FROM model_runs WHERE outcome = 'succeeded'")))
                vectors = db.scalar(text("SELECT count(*) FROM passage_embeddings"))
                revisions = db.scalar(text("SELECT count(*) FROM visualization_revisions"))
                assert {"local", "groq"} <= providers, providers
                assert vectors > 0 and revisions > 0
                print(f"Live gate persisted: providers={sorted(providers)}, vectors={vectors}, revisions={revisions}.")
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
# Telemetry names IDs, codes and durations, never private text or credentials (SECURITY.md).
for path in (root / ".local/session-api.log", root / ".local/library-worker.log"):
    if path.exists():
        logged = path.read_text(errors="replace")
        for private in ("synthetic session transport passphrase", "Before dinner, Arthur removed", "SYSTEM OVERRIDE"):
            assert private not in logged, f"{path.name} contains private text"
print("API and worker logs carry no source text or passwords.")
