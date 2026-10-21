"""Every annotated case through the real API, storage and gates, with the ideal deterministic consolidation."""

import json

import pytest
from app.models.passages import Passage
from sqlalchemy import select
from tests.conftest import ORIGIN
from tests.reconstruction_eval import DATA, evaluate, query, summary

pytestmark = pytest.mark.integration


def run_cases(api, key_prefix):
    compose, clients, work_id, story = api
    chapters = {str(p.id): p.chapter_ordinal for p in story.db.scalars(select(Passage).where(
        Passage.document_id == story.plan(None, query="Arthur").document_id))}
    reports = []
    for case in DATA["cases"]:
        body = {"query": query(case)}
        if case["through_chapter"] is not None:
            body["through_chapter_id"] = str(story.chapters[case["through_chapter"]])
        response = clients["reader"].post(f"/v1/works/{work_id}/visualizations", json=body,
                                          headers={**ORIGIN, "Idempotency-Key": f"{key_prefix}-{case['id']}"})
        assert response.status_code in {200, 201}, response.text
        reports.append(evaluate(case, response.json()["result"], chapters))
    return reports


def test_annotated_cases_end_to_end_with_the_ideal_model(api):
    reports = run_cases(api, "ideal")
    totals = summary(reports)
    print(json.dumps({"summary": totals, "reports": [r for r in reports if r["missing"] or r["incorrect"]
                                                    or r["expected"] != r["outcome"]]}, indent=1, ensure_ascii=False))
    assert totals["blocking"] == [] and totals["leaks"] == 0 and totals["incorrect"] == 0
    # Known, documented differences from the annotations: dinner candlelight never names the house, so the
    # attribution gate refuses it; the journey-attire case resolves (an inferred scar) with attire unknown.
    assert [(r["case"], r["missing"]) for r in reports if r["missing"]] == [("house-return", ["home-light"])]
    assert [r["case"] for r in reports if r["expected"] != r["outcome"]] == ["unknown-journey-attire"]
