"""Opt-in live render: one billed image request through the real API, queue and worker (DEC-51).

Set VISION_LIVE_RENDER=1 and VISION_TEST_REDIS_URL with the selected provider's key; VISION_RENDER_PROVIDER
defaults to openai (OPENAI_API_KEY), or huggingface (HF_TOKEN); VISION_RENDER_MODEL picks an approved model. The prompt comes from the synthetic
corpus's stored specification. The image is copied to .local/measurements/render-live-<model>.<ext> for review.
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from app.models.renders import RenderJob
from app.providers.images import configured_policy
from tests.test_refinement import ORIGIN, stored

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("VISION_LIVE_RENDER") != "1", reason="Set VISION_LIVE_RENDER=1 for one billed image request")]
MEASUREMENTS = Path(__file__).parents[3] / ".local/measurements"


def test_live_render_of_a_stored_specification(api, monkeypatch, tmp_path):
    provider = os.environ.get("VISION_RENDER_PROVIDER") or "openai"
    monkeypatch.setenv("VISION_RENDER_PROVIDER", provider)
    monkeypatch.setenv("VISION_RENDER_ROOT", str(tmp_path / "renders"))
    monkeypatch.setenv("REDIS_URL", os.environ["VISION_TEST_REDIS_URL"])
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", f"vision_live_{uuid.uuid4().hex}")
    original = stored(api)
    _, clients, work_id, story = api
    api_root = Path(__file__).parents[1]
    worker = subprocess.Popen([str(api_root / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1",
                               "--threads", "1", "--queues", "render"], cwd=api_root, env=os.environ.copy(),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        response = clients["reader"].post(f"/v1/works/{work_id}/visualizations/{original['id']}/renders",
                                          json={"specification_revision": original["revision"]},
                                          headers={**ORIGIN, "Idempotency-Key": "live-render"})
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["dispatched"] is True and job["model"] == configured_policy().model
        for _ in range(1800):
            view = clients["reader"].get(f"/v1/works/{work_id}/renders/{job['id']}").json()
            if view["status"] not in {"queued", "running"}:
                break
            time.sleep(0.1)
    finally:
        worker.terminate()
        worker.wait(timeout=15)
    row = story.db.get(RenderJob, uuid.UUID(job["id"]))
    story.db.refresh(row)
    report = {"provider": row.provider, "model": row.model, "status": view["status"],
              "error_code": view["error_code"], "duration_ms": row.duration_ms, "usage": row.usage,
              "settings": row.settings, "output_sha256": row.output_sha256, "media_type": row.output_media_type,
              "bytes": row.output_bytes, "prompt": original["result"]["data"]["generation"]["prompt"]}
    print(json.dumps(report, indent=2))
    assert view["status"] == "succeeded", report
    MEASUREMENTS.mkdir(parents=True, exist_ok=True)
    image = (tmp_path / "renders" / row.output_reference).read_bytes()
    name = f"render-live-{row.model.replace('/', '_')}"
    (MEASUREMENTS / f"{name}.{row.output_media_type.split('/')[1]}").write_bytes(image)
    (MEASUREMENTS / f"{name}.json").write_text(json.dumps(report, indent=2))
