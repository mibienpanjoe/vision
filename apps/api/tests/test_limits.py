"""Per-owner active-work cap over real HTTP and PostgreSQL; jobs stay queued without a broker."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.models.narrative_jobs import NarrativeJob
from app.models.works import IngestionJob, Work
from app.services.ingestion import reprocess
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.pipeline import execute_narrative
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.test_uploads import ORIGIN, readers, upload  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def capped(readers, monkeypatch):  # noqa: F811
    monkeypatch.setenv("VISION_MAX_ACTIVE_WORKS", "2")
    return readers


def works(database):
    with Session(database) as db:
        return db.scalar(select(func.count()).select_from(Work))


def finish(database, accepted):
    """Parse, then let the narrative job end; with no provider enabled it fails, which is no longer active."""
    execute_ingestion(accepted["job"]["id"])
    with Session(database) as db:
        narrative = db.scalar(select(NarrativeJob.id))
    execute_narrative(str(narrative))


def refused(response):
    assert response.status_code == 429, response.text
    error = response.json()["error"]
    assert (error["code"], error["retryable"]) == ("RESOURCE_LIMIT", True)


def test_new_work_beyond_the_cap_is_refused_before_any_source_is_stored(capped, database, tmp_path):
    alice, bruno = capped
    first = upload(alice, "one").json()
    assert upload(alice, "two").status_code == 202
    files = sorted((tmp_path / "originals").rglob("*"))
    refused(upload(alice, "three", data=b"A third book."))
    assert works(database) == 2 and sorted((tmp_path / "originals").rglob("*")) == files
    assert upload(alice, "one").json()["work"]["id"] == first["work"]["id"]  # a replay is not new work
    assert upload(bruno, "own").status_code == 202  # each owner has their own cap
    finish(database, first)
    assert upload(alice, "three", data=b"A third book.").status_code == 202


def test_retry_and_rebuild_count_as_new_active_work(capped, database, monkeypatch):
    alice, _ = capped
    first = upload(alice, "one").json()
    finish(database, first)
    second, third = upload(alice, "two").json(), upload(alice, "three", data=b"Another book.").json()
    with Session(database) as db, db.begin():
        db.execute(update(IngestionJob).where(IngestionJob.id == uuid.UUID(first["job"]["id"]))
                   .values(status="failed", stage="failed", error_code="PARSER_FAILURE", revision=IngestionJob.revision + 1))
    job = alice.get(f"/v1/works/{first['work']['id']}/ingestions/{first['job']['id']}")
    retry = alice.post(f"/v1/works/{first['work']['id']}/ingestions/{first['job']['id']}/retry",
                       headers={**ORIGIN, "Idempotency-Key": "retry", "If-Match": job.headers["etag"]})
    refused(retry)
    monkeypatch.setitem(reprocess.REVISIONS, "txt", "text-next")
    refused(alice.post(f"/v1/works/{first['work']['id']}/generations", headers={**ORIGIN, "Idempotency-Key": "next"}))
    cancelled = alice.post(f"/v1/works/{second['work']['id']}/ingestions/{second['job']['id']}/cancel",
                           headers={**ORIGIN, "Idempotency-Key": "stop", "If-Match": '"1"'})
    assert cancelled.status_code == 200, cancelled.text
    retry = alice.post(f"/v1/works/{first['work']['id']}/ingestions/{first['job']['id']}/retry",
                       headers={**ORIGIN, "Idempotency-Key": "retry-2", "If-Match": job.headers["etag"]})
    assert retry.status_code == 200, retry.text
    assert third["job"]["status"] == "queued"


def test_concurrent_uploads_cannot_exceed_the_cap(capped, database):
    alice, _ = capped
    with ThreadPoolExecutor(6) as pool:
        statuses = sorted(pool.map(lambda n: upload(alice, f"race-{n}", data=f"Book {n}.".encode()).status_code,
                                   range(6)))
    assert statuses == [202, 202, 429, 429, 429, 429] and works(database) == 2
