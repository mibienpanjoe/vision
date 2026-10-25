"""Owner-requested work deletion over real HTTP and PostgreSQL: immediate absence, conditions and stopped jobs."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.renders import RenderJob
from app.models.works import Document, IngestionJob, WorkDeletion
from sqlalchemy import inspect, select
from sqlalchemy.engine import make_url
from tests.conftest import STORY
from tests.test_refinement import ORIGIN
from tests.test_security_boundaries import (  # noqa: F401
    PUBLIC,
    SELF,
    call,
    denial,
    fingerprint,
    routes,
    world,
)

pytestmark = pytest.mark.integration
DELETE = ("DELETE", "/v1/works/{work_id}")


def delete(client, work_id, key="delete-one", match='"1"'):
    headers = {**ORIGIN, "Idempotency-Key": key, **({"If-Match": match} if match is not None else {})}
    return client.delete(f"/v1/works/{work_id}", headers=headers)


def test_a_deleted_work_is_absent_from_every_route_at_once(world):  # noqa: F811
    clients, story, ids, other, bodies, extra = world
    reader, work = clients["reader"], ids["work_id"]
    assert reader.get(f"/v1/works/{work}").headers["etag"] == '"1"'
    accepted = delete(reader, work)
    assert accepted.status_code == 202, accepted.text
    assert accepted.json()["status"] == "pending" and accepted.json()["completed_at"] is None
    unknown = {key: str(uuid.uuid4()) if key != "number" else "1" for key in ids}
    for method, template in sorted(r for r in routes() - PUBLIC - SELF - {DELETE} if "{work_id}" in r[1]):
        missing = denial(call(reader, method, template, unknown, {k: str(uuid.uuid4()) for k in extra}, bodies))
        assert denial(call(reader, method, template, ids, extra, bodies)) == missing, (method, template)
    assert [w["id"] for w in reader.get("/v1/works").json()["items"]] == [other]
    assert reader.get(f"/v1/works/{other}").status_code == 200
    # The tombstone keeps lifecycle facts only; the work row waits for the purge.
    tombstone = story.db.get(WorkDeletion, uuid.UUID(work))
    assert (tombstone.status, tombstone.expected_revision) == ("pending", 1)
    assert {column.key for column in WorkDeletion.__table__.columns} == {
        "work_id", "owner_id", "idempotency_key", "expected_revision", "status", "attempts", "requested_at",
        "dispatched_at", "completed_at"}


def test_deletion_is_conditional_owner_only_and_replayable(world, database):  # noqa: F811
    clients, story, ids, *_ = world
    reader, stranger, work = clients["reader"], clients["stranger"], ids["work_id"]
    before = fingerprint(database)
    assert delete(stranger, work).status_code == 404
    assert delete(reader, work, match=None).status_code == 428
    assert delete(reader, work, match='"2"').status_code == 412
    assert fingerprint(database) == before
    first = delete(reader, work)
    assert first.status_code == 202
    assert delete(reader, work).json() == first.json()  # the exact request replays
    assert delete(reader, work, key="another").status_code == 404
    assert delete(reader, work, match='"2"').status_code == 404
    assert delete(stranger, work).status_code == 404


def test_deletion_stops_queued_work_and_flags_running_work(world):  # noqa: F811
    clients, story, ids, other, *_ = world
    db, work = story.db, uuid.UUID(ids["work_id"])
    ingestion = db.scalar(select(IngestionJob).join(Document).where(Document.work_id == work))
    ingestion.status = "queued"
    render = db.get(RenderJob, uuid.UUID(ids["job_id"]))
    render.status = "running"
    db.commit()
    revisions = ingestion.revision, render.revision
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
    db.expire_all()
    assert (ingestion.status, ingestion.cancel_requested, ingestion.revision) == ("cancelled", True, revisions[0] + 1)
    assert (render.status, render.cancel_requested, render.revision) == ("running", True, revisions[1] + 1)
    narratives = dict(db.execute(select(Document.work_id, NarrativeJob.status).join(
        SourceGeneration, SourceGeneration.document_id == Document.id).join(
        NarrativeJob, NarrativeJob.generation_id == SourceGeneration.id)).all())
    assert narratives == {work: "cancelled", uuid.UUID(other): "queued"}  # the other work is untouched


def test_an_upload_key_of_a_deleted_work_is_never_replayed(world):  # noqa: F811
    clients, story, ids, *_ = world
    reader = clients["reader"]
    assert delete(reader, ids["work_id"]).status_code == 202
    replay = reader.post("/v1/works", data={"title": "Plans", "format": "md"},
                         files={"file": ("story.md", STORY.read_bytes())},
                         headers={**ORIGIN, "Idempotency-Key": "plan-source"})
    assert replay.status_code == 409, replay.text
    assert "Plans" not in replay.text and ids["work_id"] not in replay.text


def test_deletion_migration_round_trips_without_touching_live_works(world):  # noqa: F811
    clients, story, ids, other, *_ = world
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database == story.engine.url.database and target.database.startswith("vision_test_")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    story.db.close()
    command.downgrade(config, "0023")
    with story.engine.connect() as connection:
        assert not inspect(connection).has_table("work_deletions")
        assert "deleted_at" not in {c["name"] for c in inspect(connection).get_columns("works")}
    command.upgrade(config, "head")
    assert clients["reader"].get(f"/v1/works/{other}").status_code == 200
    assert delete(clients["reader"], ids["work_id"]).status_code == 202
