import pytest
from app.main import create_app
from app.models.passages import Chapter
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


def test_chapter_numbers_are_owned_current_and_paginated_without_titles(story):
    work_id = story.plan(None, query="Arthur").work_id
    current = story.db.scalar(select(Chapter).where(Chapter.id == story.chapters[1]))
    story.db.add(Chapter(document_id=current.document_id, parser_revision="obsolete-test", ordinal=99,
                         title="A future identity revealed", source_start=0, source_end=1))
    story.db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        client.post("/v1/auth/login", json={"username": "reader", "password": "synthetic query plan passphrase"}, headers=ORIGIN)
        endpoint = f"/v1/works/{work_id}/chapters"
        first = client.get(endpoint, params={"limit": 2})
        assert first.status_code == 200
        page = first.json()
        assert page["generation_id"] == str(story.generation)
        assert page["items"] == [{"id": str(story.chapters[n]), "ordinal": n} for n in (1, 2)]
        assert page["next_after"] == 2
        second = client.get(endpoint, params={"limit": 2, "after": page["next_after"]}).json()
        assert [item["ordinal"] for item in second["items"]] == [3, 4]
        last = client.get(endpoint, params={"after": second["next_after"]}).json()
        assert last["items"] == [{"id": str(story.chapters[5]), "ordinal": 5}]
        assert last["next_after"] is None
        assert client.get(endpoint, params={"limit": 101}).status_code == 422
        client.post("/v1/auth/login", json={"username": "stranger", "password": "synthetic query plan passphrase"}, headers=ORIGIN)
        assert client.get(endpoint).status_code == 404


def test_unparsed_source_has_no_invented_chapters(story):
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        client.post("/v1/auth/login", json={"username": "reader", "password": "synthetic query plan passphrase"}, headers=ORIGIN)
        accepted = client.post("/v1/works", data={"title": "Unparsed", "format": "txt"},
                               files={"file": ("source.txt", b"Chapter 1\n\nA story.")},
                               headers={**ORIGIN, "Idempotency-Key": "unparsed-chapters"}).json()
        response = client.get(f"/v1/works/{accepted['work']['id']}/chapters")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SOURCE_NOT_READY"
