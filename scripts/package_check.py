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


def call(opener, method, path, body=None, headers=None, raw=False):
    headers = {"Origin": web, **(headers or {})}
    data = None
    if isinstance(body, dict):
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    elif body is not None:
        data, headers["Content-Type"] = body
    request = urllib.request.Request(web + "/api/v1" + path, data=data, method=method, headers=headers)
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
        print("Packaged stack passed: readiness, worker narrative, private storage, owner isolation, restart.")
    finally:
        compose("logs", "--no-color", stdout=open(root / ".local/package-check.log", "w"), check=False)
        compose("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()
