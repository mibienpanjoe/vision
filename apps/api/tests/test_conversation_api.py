import uuid

import pytest
from app.models.conversations import Conversation
from sqlalchemy import select

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


def test_create_replay_list_and_owner_denial(api):
    _, clients, work_id, story = api
    reader, stranger = clients["reader"], clients["stranger"]
    body = {"work_id": work_id, "title": "Arthur's portrait"}
    first = reader.post("/v1/conversations", json=body, headers={**ORIGIN, "Idempotency-Key": "thread"})
    assert first.status_code == 201, first.text
    found = first.json()
    assert first.headers["etag"] == '"1"' and found["card"] is None and found["active_turn"] is None
    assert reader.post("/v1/conversations", json=body, headers={**ORIGIN, "Idempotency-Key": "thread"}).json() == found
    assert reader.post("/v1/conversations", json={**body, "title": "Other"}, headers={**ORIGIN, "Idempotency-Key": "thread"}).status_code == 409
    assert reader.get(f'/v1/conversations/{found["id"]}').json() == found
    assert reader.get("/v1/conversations").json()["items"][0]["id"] == found["id"]
    for suffix in ["", "/messages", "/cards/1", "/turns/" + str(uuid.uuid4())]:
        assert stranger.get(f'/v1/conversations/{found["id"]}{suffix}').status_code == 404
    assert stranger.get("/v1/conversations").json()["items"] == []
    assert stranger.post("/v1/conversations", json=body, headers={**ORIGIN, "Idempotency-Key": "stolen"}).status_code == 404
    assert reader.post("/v1/conversations", json=body, headers={"Idempotency-Key": "no-origin"}).status_code == 403
    assert len(list(story.db.scalars(select(Conversation)))) == 1


def test_bounded_stable_pagination_and_strict_inputs(api):
    _, clients, work_id, _ = api
    client = clients["reader"]
    ids = []
    for n in range(5):
        response = client.post("/v1/conversations", json={"work_id": work_id, "title": f"Portrait {n}"}, headers={**ORIGIN, "Idempotency-Key": f"thread-{n}"})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    page = client.get("/v1/conversations?limit=2").json()
    seen = [item["id"] for item in page["items"]]
    while page["next_cursor"]:
        page = client.get(f'/v1/conversations?limit=2&after={page["next_cursor"]}').json()
        seen.extend(item["id"] for item in page["items"])
    assert seen == list(reversed(ids)) and len(set(seen)) == 5
    for url in ["/v1/conversations?limit=0", "/v1/conversations?limit=51", "/v1/conversations?after=invalid"]:
        assert client.get(url).status_code == 422
    assert client.post("/v1/conversations", json={"work_id": work_id, "owner_id": str(uuid.uuid4())}, headers={**ORIGIN, "Idempotency-Key": "forged"}).status_code == 422
    assert client.get(f'/v1/conversations/{ids[0]}/messages').json() == {"items": [], "next_after": None}


def test_message_pages_and_tombstoned_thread_are_owned(api):
    from app.core.security import ActorScope
    from app.models.access import Principal
    from app.services.conversations import store
    _, clients, work_id, story = api
    db = story.db
    owner = db.scalar(select(Principal).where(Principal.username == "reader"))
    actor = ActorScope(owner.id, owner.username)
    thread = store.create(db, actor, uuid.UUID(work_id), "Long thread", "long-thread")
    for n in range(7):
        store.enqueue(db, actor, thread.id, f'"{n + 1}"', f"turn-{n}", {"text": f"Message {n}"}, "test")
    db.commit()
    client = clients["reader"]
    page = client.get(f"/v1/conversations/{thread.id}/messages?limit=3").json()
    rows = page["items"]
    while page["next_after"]:
        page = client.get(f'/v1/conversations/{thread.id}/messages?limit=3&after={page["next_after"]}').json()
        rows.extend(page["items"])
    assert [m["sequence"] for m in rows] == list(range(1, 8))
    assert [m["content"] for m in rows] == [f"Message {n}" for n in range(7)]
    assert client.get(f'/v1/conversations/{thread.id}/turns/{rows[-1]["turn_id"]}').json()["dispatch_pending"]
    removed = client.delete(f"/v1/works/{work_id}", headers={**ORIGIN, "Idempotency-Key": "delete", "If-Match": '"1"'})
    assert removed.status_code == 202
    assert client.get(f"/v1/conversations/{thread.id}").status_code == 404
    assert client.get(f"/v1/conversations/{thread.id}/messages").status_code == 404
    assert client.get("/v1/conversations").json()["items"] == []
