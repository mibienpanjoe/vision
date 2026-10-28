"""Opt-in live evaluation: real worker with local models and configured text inference.

Set VISION_LIVE_RECONSTRUCTION=1 with the selected provider's key and local model weights. The synthetic corpus is
uploaded through the API, ingested by a real Dramatiq worker in local mode, and every annotated case is
requested through the stored-visualization route. Groq is paced once a minute by default; OpenAI defaults
to no deliberate delay. Reports stay local and separate from the historical Groq baseline.
"""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.model_runs import Derivation, ModelRun
from app.models.passages import Chapter, Passage
from app.services.dispatch import dispatch_ingestions
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import ORIGIN, STORY
from tests.reconstruction_eval import DATA, SCORER_VERSION, evaluate, query, summary
from tests.reconstruction_trace import CallBudget, CaptureAdapter, call_metadata

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("VISION_LIVE_RECONSTRUCTION") != "1", reason="Set VISION_LIVE_RECONSTRUCTION=1 for the live run")]
PROVIDER = os.environ.get("VISION_QUERY_PROVIDER", "groq")
PACE = float(os.environ.get("VISION_LIVE_PACE", "0" if PROVIDER == "openai" else "65"))


def test_live_reconstruction_of_every_annotated_case(database, monkeypatch, tmp_path, request):
    from app.services.visualization.specification import consolidation_adapter

    adapter = consolidation_adapter()
    assert adapter is not None
    assert hashlib.sha256(STORY.read_bytes()).hexdigest() == DATA["source_sha256"]
    # Capture only this pinned synthetic corpus, never application/private-book traffic.
    from app.services.visualization import specification
    capture = CaptureAdapter(adapter)
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: capture)
    budget = CallBudget(50)
    stage_trace, results, passage_chapters = [], [], {}
    trace = Path(__file__).parents[3] / ".local/measurements" / (
        f"reconstruction-{adapter.provider}-{adapter.model}-{getattr(adapter, 'effort', 'default')}-{SCORER_VERSION}-trace.json")
    def save_trace():
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text(json.dumps({"scorer_version": SCORER_VERSION, "source_sha256": DATA["source_sha256"],
                                     "cases": results, "all_calls": capture.calls, "all_stages": stage_trace,
                                     "passage_chapters": passage_chapters, **call_metadata(capture, budget)}, indent=1, ensure_ascii=False))
    request.addfinalizer(save_trace)  # Retain charged attempts even if a case raises before its result is scored.
    verify = specification.verify_state
    def traced_verify(*args, **kwargs):
        result = verify(*args, **kwargs)
        stage_trace.append({"stage": "verification", "removed": {str(k): v for k, v in result.removed.items()},
                            "adjudication": result.adjudication})
        return result
    monkeypatch.setattr(specification, "verify_state", traced_verify)
    prompt_gate = specification.prompt_problems
    def traced_gate(*args, **kwargs):
        problems = prompt_gate(*args, **kwargs)
        stage_trace.append({"stage": "prompt_gate", "prompt": args[0], "excluded": args[2], "problems": problems})
        return problems
    monkeypatch.setattr(specification, "prompt_problems", traced_gate)
    scene = specification.scene
    def traced_scene(*args, **kwargs):
        composed, labels = scene(*args, **kwargs)
        members = [*composed.members, *composed.world] if hasattr(composed, "members") else []
        stage_trace.append({"stage": "reconstruction", "outcome": composed.outcome, "members": [
            {"label": m.entity.label, "event": str(m.state.event),
             "traits": {k: {"status": t.status, "values": t.values, "facts": list(map(str, t.facts))}
                        for k, t in m.state.traits.items()},
             "excluded": {str(k): v for k, v in m.state.excluded.items()}} for m in members]})
        return composed, labels
    monkeypatch.setattr(specification, "scene", traced_scene)
    if PROVIDER == "openai":
        # This opt-in evaluation is finite, not a loop that can spend indefinitely on bad responses.
        from app.providers.openai_responses import OpenAIResponses
        complete = OpenAIResponses.complete

        def bounded(self, call):
            budget.take()
            return complete(self, call)

        monkeypatch.setattr(OpenAIResponses, "complete", bounded)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    monkeypatch.setenv("REDIS_URL", os.environ["VISION_TEST_REDIS_URL"])
    monkeypatch.setenv("VISION_QUEUE_NAMESPACE", f"vision_live_{os.getpid()}")
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    with Session(database) as db:
        db.add(Principal(username="live", password_hash=hash_password("synthetic live passphrase")))
        db.commit()
    api = Path(__file__).parents[1]
    with TestClient(create_app(), base_url="http://127.0.0.1") as client, \
            (tmp_path / "worker.log").open("w") as log:
        assert client.post("/v1/auth/login", json={"username": "live", "password": "synthetic live passphrase"},
                           headers=ORIGIN).status_code == 200
        worker = subprocess.Popen([str(api / ".venv/bin/dramatiq"), "app.workers.bootstrap", "--processes", "1",
                                   "--threads", "1"], cwd=api, env=os.environ.copy(), stdout=log, stderr=log)
        try:
            started = time.monotonic()
            work = client.post("/v1/works", data={"title": "Live", "format": "md"},
                               files={"file": ("story.md", STORY.read_bytes())},
                               headers={**ORIGIN, "Idempotency-Key": "live-source"}).json()
            work_id = work["work"]["id"]
            dispatch_ingestions(database)
            for _ in range(3600):
                generation = client.get(f"/v1/works/{work_id}/generations").json()["items"][0]
                if generation["narrative_status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.5)
            assert generation["narrative_status"] == "succeeded", (tmp_path / "worker.log").read_text()[-2000:]
            ingestion_s = round(time.monotonic() - started, 1)
        finally:
            worker.terminate()
            worker.wait(timeout=15)

        with Session(database) as db:
            chapters = {c.ordinal: str(c.id) for c in db.scalars(select(Chapter).where(
                Chapter.document_id == work["work"]["document_id"]))}
            passage_chapters = {str(p.id): p.chapter_ordinal for p in db.scalars(select(Passage).where(
                Passage.document_id == work["work"]["document_id"]))}
        reports, costs = [], []
        for i, case in enumerate(DATA["cases"]):
            if i:
                time.sleep(PACE)
            body = {"query": query(case)}
            if case["through_chapter"] is not None:
                body["through_chapter_id"] = chapters[case["through_chapter"]]
            with Session(database) as db:
                seen = {r for r in db.scalars(select(ModelRun.id))}
            call_start, stage_start = len(capture.calls), len(stage_trace)
            clock = time.monotonic()
            response = client.post(f"/v1/works/{work_id}/visualizations", json=body,
                                   headers={**ORIGIN, "Idempotency-Key": f"live-{case['id']}"})
            elapsed = round(time.monotonic() - clock, 2)
            assert response.status_code in {200, 201}, response.text
            result = response.json()["result"]
            with Session(database) as db:
                runs = [r for r in db.scalars(select(ModelRun)) if r.id not in seen]
                publication = [{"id": str(d.id), "rejections": d.rejections, "scope": d.scope} for d in
                               db.scalars(select(Derivation).where(Derivation.id.in_(
                                   {r.derivation_id for r in runs if r.derivation_id})))]
            results.append({"case": case["id"], "result": result, "publication": publication,
                            "verification": stage_trace[stage_start:], "calls": capture.calls[call_start:]})
            save_trace()
            costs.append({"case": case["id"], "seconds": elapsed, "outcome": result["outcome"],
                          "error": result.get("error", {}).get("code"),
                          "calls": [(r.purpose, r.outcome, r.input_tokens, r.output_tokens, r.duration_ms) for r in runs]})
            reports.append(evaluate(case, result, passage_chapters))
            print(json.dumps({"case": case["id"], "outcome": result["outcome"], "seconds": elapsed,
                              "provider_calls": len(runs)}, ensure_ascii=False), flush=True)
    totals = summary(reports)
    tokens = sum((c[2] or 0) + (c[3] or 0) for cost in costs for c in cost["calls"])
    input_tokens = sum(c[2] or 0 for cost in costs for c in cost["calls"])
    output_tokens = sum(c[3] or 0 for cost in costs for c in cost["calls"])
    report = {"scorer_version": SCORER_VERSION, "provider": adapter.provider, "model": adapter.model,
              "configuration": getattr(adapter, "configuration", {}),
              **call_metadata(capture, budget),
              "ingestion_s": ingestion_s, "summary": totals, "tokens": tokens,
              "input_tokens": input_tokens, "output_tokens": output_tokens,
              "seconds": sum(c["seconds"] for c in costs), "costs": costs, "reports": reports}
    if adapter.provider == "openai" and adapter.model == "gpt-6-luna":
        report["estimated_standard_usd"] = (input_tokens * 0.10 + output_tokens * 0.50) / 1_000_000
    suffix = f"-{adapter.provider}-{adapter.model}-{adapter.effort}" if adapter.provider == "openai" else "-live"
    out = Path(__file__).parents[3] / f".local/measurements/reconstruction{suffix}-{SCORER_VERSION}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: report[k] for k in ("ingestion_s", "summary", "tokens", "seconds")}, indent=1))
    assert not budget.exhausted, "Evaluation incomplete: OpenAI transport attempt cap reached"
    assert totals["blocking"] == []
