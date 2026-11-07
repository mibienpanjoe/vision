import uuid

import pytest
from app.core.security import ActorScope
from app.models.access import Principal
from app.models.generations import SourceGeneration
from app.models.narrative_jobs import NarrativeJob
from app.models.works import IngestionJob, Work
from app.services.conversations import store, turns
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.test_conversation_turns import post

pytestmark = pytest.mark.integration


def failed_book(api, monkeypatch, *, parsing=False, fatal=False, attempts=1):
    monkeypatch.delenv("REDIS_URL", raising=False)
    _, clients, work_id, story = api
    with Session(story.engine) as db, db.begin():
        owner = db.scalar(select(Principal).where(Principal.username == "reader"))
        actor = ActorScope(owner.id, owner.username)
        generation = db.get(SourceGeneration, story.generation)
        generation.narrative_ready_at = generation.search_ready_at = None
        model = IngestionJob if parsing else NarrativeJob
        job = db.scalar(select(model).where(model.generation_id == generation.id))
        job.status, job.error_code, job.attempts = "failed", "TEXT_LAYER_UNAVAILABLE" if fatal else "PROVIDER_UNAVAILABLE", attempts
        thread = store.create(db, actor, uuid.UUID(work_id), "Portrait", "thread")
        turn = store.enqueue(db, actor, thread.id, '"1"', "question", {"text": "Arthur after the war at home"}, "test")
        turns.finish(db, thread, turn, "failed", "Book preparation failed.", error_code="BOOK_PREPARATION_FAILED")
        thread_id, job_id = thread.id, job.id
    return clients, story, thread_id, job_id


@pytest.mark.parametrize("parsing", [False, True])
def test_retry_reuses_original_and_question_and_replays_lost_response(api, monkeypatch, parsing):
    clients, story, thread_id, job_id = failed_book(api, monkeypatch, parsing=parsing)
    path = f"/v1/conversations/{thread_id}/preparation-retries"
    view = clients["reader"].get(f"/v1/conversations/{thread_id}").json()
    original = clients["reader"].get(f'/v1/works/{view["work_id"]}/original').content
    response = post(clients["reader"], path, {}, "retry", 3)
    assert response.status_code == 202, response.text
    turn = response.json()
    assert turn["status"] == "waiting_for_book"
    assert post(clients["reader"], path, {}, "retry", 3).json()["id"] == turn["id"]
    assert post(clients["reader"], path, {}, "another", 3).status_code == 412
    assert post(clients["stranger"], path, {}, "steal", 4).status_code == 404
    with Session(story.engine) as db:
        job = db.get(IngestionJob if parsing else NarrativeJob, job_id)
        assert job.status == "queued" and job.attempts == 1 and job.dispatched_at is None
        assert db.scalar(select(func.count()).select_from(Work)) == 2
    assert clients["reader"].get(f'/v1/works/{view["work_id"]}/original').content == original
    assert post(clients["reader"], path, {"owner_id": "forged"}, "forged", 4).status_code == 422
    messages = clients["reader"].get(f"/v1/conversations/{thread_id}/messages").json()["items"]
    assert [m["content"] for m in messages] == ["Arthur after the war at home", "Book preparation failed.", "Retry book preparation."]


@pytest.mark.parametrize("fatal,attempts,status", [(True, 1, 409), (False, 3, 429)])
def test_retry_rejects_unrecoverable_or_exhausted_source_without_mutation(api, monkeypatch, fatal, attempts, status):
    clients, story, thread_id, job_id = failed_book(api, monkeypatch, parsing=True, fatal=fatal, attempts=attempts)
    path = f"/v1/conversations/{thread_id}/preparation-retries"
    assert post(clients["reader"], path, {}, "retry", 3).status_code == status
    with Session(story.engine) as db:
        assert db.get(IngestionJob, job_id).status == "failed"
    assert clients["reader"].get(f"/v1/conversations/{thread_id}").json()["revision"] == 3


@pytest.mark.parametrize("stage", ["parse", "narrative"])
def test_retry_after_worker_failure_finishes_the_original_question(api, monkeypatch, tmp_path, stage):
    from tests.test_conversation_attachments import ROOT, upload_worker, wait
    from tests.test_conversation_turns import setup, stop
    client, _, story, _ = setup(api, monkeypatch)
    marker = tmp_path / "failure"
    marker.touch()
    monkeypatch.setenv("VISION_TEST_PARSE_GATE", str(tmp_path / "unused-gate"))
    monkeypatch.setenv("VISION_TEST_WORKSPACE", "1")
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    monkeypatch.setenv("VISION_TEST_PARSE_FAILURE" if stage == "parse" else "VISION_TEST_NARRATIVE_FAILURE", str(marker))
    source = (ROOT / "narrative/story.md").read_bytes()
    uploaded = client.post("/v1/works", files={"file": ("book.md", source)},
                           headers={"Origin": "http://127.0.0.1:3000", "Idempotency-Key": "book"}).json()
    work_id = uploaded["work"]["id"]
    thread = post(client, "/v1/conversations", {"work_id": work_id}, "thread-new").json()
    question = "Arthur after the war at home"
    post(client, f'/v1/conversations/{thread["id"]}/turns', {"text": question}, "question", 1)
    path = f'/v1/conversations/{thread["id"]}'
    worker = None
    with (tmp_path / "worker.log").open("w") as log:
        try:
            worker = upload_worker(log)
            failed = wait(client, path, "failed", seconds=60)
            assert failed["active_turn"]["error_code"] == "BOOK_PREPARATION_FAILED"
            marker.unlink()
            retry = post(client, path + "/preparation-retries", {}, "retry", failed["revision"])
            assert retry.status_code == 202, retry.text
            ready = wait(client, path, "succeeded", seconds=60)
            assert ready["card"] is not None
            assert client.get(f"/v1/works/{work_id}/original").content == source
            with Session(story.engine) as db:
                assert db.scalar(select(func.count()).select_from(Work)) == 3
            messages = client.get(path + "/messages").json()["items"]
            assert [m["content"] for m in messages if m["role"] == "user"] == [question, "Retry book preparation."]
        finally:
            stop(worker)
