"""Run the packaged images as an isolated compose project and exercise a real two-owner flow through the web proxy.

Uses its own project name, ports and volumes, so the development database is untouched, and removes everything it
created afterwards. Build the images first (`make images`).
"""

import http.cookiejar
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
project = "vision-package-" + uuid.uuid4().hex[:8]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


ports = {"POSTGRES_PORT": free_port(), "REDIS_PORT": free_port(), "VISION_WEB_PORT": free_port()}
web = f"http://127.0.0.1:{ports['VISION_WEB_PORT']}"
password = "synthetic package check passphrase"
story = (root / "apps/api/tests/fixtures/narrative/story.md").read_bytes()


def compose(*args, check=True, **kwargs):
    return subprocess.run(["docker", "compose", "-p", project, "--profile", "app", *args], cwd=root,
                          env={**os.environ, **ports}, check=check, text=True, **kwargs)


def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(opener, method, path, body=None, headers=None, raw=False, base=None):
    base = base or web
    headers = {"Origin": base, **(headers or {})}
    data = None
    if isinstance(body, dict):
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    elif body is not None:
        data, headers["Content-Type"] = body
    request = urllib.request.Request(base + "/api/v1" + path, data=data, method=method, headers=headers)
    try:
        with opener.open(request, timeout=30) as response:
            content = response.read()
            return response.status, content if raw else json.loads(content or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def multipart(title):
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="format"\r\n\r\nmd\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="story.md"\r\n'
             f'Content-Type: text/markdown\r\n\r\n'.encode() + story + b"\r\n", f"--{boundary}--\r\n".encode()]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def recovery_drill(reader, kept_work):
    """Actual stopped-volume backup -> new Compose project -> newer-deletion replay -> private HTTP reads."""
    status, accepted = call(reader, "POST", "/works", multipart("Delete after snapshot"),
                            {"Idempotency-Key": "delete-after-snapshot"})
    assert status == 202, accepted
    deleted_work = accepted["work"]["id"]
    archive = root / ".local" / ("snapshot-" + uuid.uuid4().hex)
    ledger = root / ".local" / ("deletions-" + uuid.uuid4().hex + ".json")
    values = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines()
                  if line and not line.startswith("#"))
    template = urllib.parse.urlsplit(values["DATABASE_URL"])

    def snapshot(command, name, target_ports, *args):
        url = urllib.parse.urlunsplit((template.scheme,
            f"{template.username}:{template.password}@127.0.0.1:{target_ports['POSTGRES_PORT']}", "/vision", "", ""))
        subprocess.run([str(root / "apps/api/.venv/bin/python"), "-m", "app.operations", command, *map(str, args)],
            cwd=root / "apps/api", env={**os.environ, **target_ports, "COMPOSE_PROJECT_NAME": name, "DATABASE_URL": url},
            check=True)

    compose("stop", "web", "api", "worker")
    started = time.monotonic()
    snapshot("backup", project, ports, archive, "--packaged")
    compose("up", "-d", "--wait", "--no-build", "api", "worker", "web")
    revision = call(reader, "GET", f"/works/{deleted_work}")[1]["revision"]
    headers = {"Idempotency-Key": "delete-for-restore", "If-Match": f'"{revision}"'}
    assert call(reader, "DELETE", f"/works/{deleted_work}", headers=headers)[0] == 202
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if call(reader, "DELETE", f"/works/{deleted_work}", headers=headers)[1]["status"] == "completed":
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Source deletion did not finish")
    compose("stop", "web", "api", "worker")
    snapshot("deletions", project, ports, ledger)
    target = "vision-restore-" + uuid.uuid4().hex[:8]
    target_ports = {"POSTGRES_PORT": free_port(), "REDIS_PORT": free_port(), "VISION_WEB_PORT": free_port(),
                    "VISION_QUEUE_NAMESPACE": target}
    target_web = f"http://127.0.0.1:{target_ports['VISION_WEB_PORT']}"

    def restored(*args, **kwargs):
        return subprocess.run(["docker", "compose", "-p", target, "--profile", "app", *args], cwd=root,
            env={**os.environ, **target_ports}, text=True, **kwargs)

    try:
        restored("up", "-d", "--wait", "db", "redis", check=True)
        restored("create", "--no-build", "api", check=True)
        snapshot("restore", target, target_ports, archive, "--deletions", ledger, "--packaged")
        restored("up", "-d", "--wait", "--no-build", "api", "worker", "web", check=True)
        # Restored sessions are deliberately invalid, including cookies from the original environment.
        assert call(reader, "GET", f"/works/{kept_work}", base=target_web)[0] == 401
        for username, expected in (("package_reader", 200), ("package_stranger", 404)):
            opener = client()
            assert call(opener, "POST", "/auth/login", {"username": username, "password": password},
                        base=target_web)[0] == 200
            status, original = call(opener, "GET", f"/works/{kept_work}/original", raw=True, base=target_web)
            assert status == expected
            if expected == 200:
                assert original == story
                assert call(opener, "DELETE", f"/works/{deleted_work}", headers=headers,
                            base=target_web)[1]["status"] == "completed"
            assert call(opener, "GET", f"/works/{deleted_work}", base=target_web)[0] == 404
        subprocess.run(["pnpm", "--dir", "apps/web", "exec", "playwright", "test", "--config",
                        "playwright.restore.config.ts"], cwd=root,
                       env={**os.environ, "VISION_TEST_RESTORE_ORIGIN": target_web}, check=True)
        print(f"Packaged restore passed in {time.monotonic() - started:.1f}s: new database/volumes, exact original, "
              "owner isolation, revoked sessions and newer deletion replay.")
    finally:
        with (root / ".local/restore-package-check.log").open("w") as log:
            restored("logs", "--no-color", stdout=log, check=False)
        restored("down", "-v", "--remove-orphans", check=False)


def main():
    try:
        compose("up", "-d", "--wait", "--no-build")
        for name in ("package_reader", "package_stranger"):
            compose("exec", "-T", "api", "python", "-m", "app.cli", "create-user", name, "--password-stdin",
                    input=password + "\n", capture_output=True)
        reader, stranger = client(), client()
        for opener, name in ((reader, "package_reader"), (stranger, "package_stranger")):
            status, _ = call(opener, "POST", "/auth/login", {"username": name, "password": password})
            assert status == 200, status
        status, accepted = call(reader, "POST", "/works", multipart("Packaged"), {"Idempotency-Key": "package"})
        assert status == 202, accepted
        work, job = accepted["work"]["id"], accepted["job"]["id"]
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            generation = call(reader, "GET", f"/works/{work}/generations")[1]["items"][0]
            if generation.get("narrative_status") in {"succeeded", "failed"}:
                break
            time.sleep(3)
        print("ingestion:", call(reader, "GET", f"/works/{work}/ingestions/{job}")[1]["status"],
              "narrative:", generation.get("narrative_status"))
        assert generation["narrative_status"] == "succeeded", generation
        entities = call(reader, "GET", f"/works/{work}/entities")[1]["items"]
        assert any(e["label"] == "Arthur" for e in entities), entities
        status, original = call(reader, "GET", f"/works/{work}/original", raw=True)
        assert (status, original) == (200, story)
        assert call(stranger, "GET", f"/works/{work}/original")[0] == 404
        assert call(stranger, "GET", f"/works/{work}")[0] == 404
        assert call(client(), "GET", f"/works/{work}")[0] == 401
        modes = compose("exec", "-T", "api", "sh", "-c", "stat -c '%a %U' /data/originals /data/originals/*",
                        capture_output=True).stdout.split("\n")
        assert modes[0] == "700 vision" and all(m == "600 vision" for m in modes[1:] if m), modes
        baked = compose("exec", "-T", "api", "sh", "-c", "ls -a /app; test ! -e /app/.env && echo no-env",
                        capture_output=True).stdout
        assert "no-env" in baked and "tests" not in baked.split(), baked
        published = compose("ps", "--format", "{{.Service}} {{.Publishers}}", capture_output=True).stdout
        assert all("8000" not in line for line in published.splitlines() if line.startswith("api")), published
        web_log = compose("logs", "--no-color", "web", capture_output=True).stdout
        assert "download" not in web_log.lower(), web_log
        stopped = time.monotonic()
        compose("stop", "worker")
        state = subprocess.run(["docker", "inspect", "-f", "{{.State.ExitCode}}",
                                compose("ps", "-aq", "worker", capture_output=True).stdout.strip()],
                               capture_output=True, text=True).stdout.strip()
        print(f"worker stopped with exit code {state} in {time.monotonic() - stopped:.1f}s")
        assert state == "0"
        compose("restart", "api")
        compose("up", "-d", "--wait", "--no-build", "api", "web", "worker")
        assert call(reader, "GET", f"/works/{work}/original", raw=True) == (200, story)
        recovery_drill(reader, work)
        print("Packaged stack passed: readiness, worker narrative, private storage, owner isolation, restart.")
    finally:
        compose("logs", "--no-color", stdout=open(root / ".local/package-check.log", "w"), check=False)
        compose("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()
