"""Owner-only render history and private image delivery over real HTTP/PostgreSQL storage."""

import uuid

import pytest
from app.models.renders import RenderJob
from app.services.visualization import render
from tests.image_fixtures import PNG
from tests.test_refinement import refine, stored
from tests.test_render_contract import Recording, current, enable, execute, submit

pytestmark = pytest.mark.integration


def image(api, job, client="reader", **params):
    _, clients, work_id, _ = api
    return clients[client].get(f"/v1/works/{work_id}/renders/{job['id']}/image", params=params)


def history(api, view, client="reader"):
    _, clients, work_id, _ = api
    return clients[client].get(f"/v1/works/{work_id}/visualizations/{view['id']}/renders")


def test_owner_reads_exact_private_image_and_history_marks_older_specifications(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch, 2)
    job = submit(api, original).json()
    execute(monkeypatch, Recording(), job)
    response = image(api, job)
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["etag"] == f'"{current(api, job)["output_sha256"]}"'
    assert response.headers["content-disposition"].startswith("inline;")
    assert image(api, job, download="true").headers["content-disposition"].startswith("attachment;")
    page = history(api, original).json()
    assert page["current_revision"] == 1 and [item["id"] for item in page["items"]] == [job["id"]]
    newer = refine(api, original).json()
    second = submit(api, newer, key="second").json()
    page = history(api, original).json()
    assert page["current_revision"] == 2
    assert [(item["id"], item["specification_revision"]) for item in page["items"]] == [
        (second["id"], 2), (job["id"], 1)]
    # The reserved snapshot is the revision a reader reopens; its evidence is unchanged by later edits.
    _, clients, work_id, story = api
    revision = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}/revisions/1").json()
    row = story.db.get(RenderJob, uuid.UUID(job["id"]))
    assert revision["result"]["data"] == row.specification == original["result"]["data"]


def test_other_owners_and_other_works_cannot_read_or_list_renders(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch)
    job = submit(api, original).json()
    execute(monkeypatch, Recording(), job)
    _, clients, work_id, story = api
    stranger = image(api, job, client="stranger")
    assert stranger.status_code == 404 and stranger.content != PNG
    assert history(api, original, client="stranger").status_code == 404
    other_work = story.db.get(RenderJob, uuid.UUID(job["id"])).work_id
    assert other_work == uuid.UUID(work_id)
    with_other_work = clients["reader"].get(f"/v1/works/{uuid.uuid4()}/renders/{job['id']}/image")
    assert with_other_work.status_code == 404
    assert clients["reader"].get(f"/v1/works/{work_id}/renders/{uuid.uuid4()}/image").status_code == 404


@pytest.mark.parametrize("damage", ["missing", "altered"])
def test_missing_or_altered_storage_is_never_served_as_the_render(api, monkeypatch, renders, damage):
    original = stored(api)
    enable(monkeypatch)
    job = submit(api, original).json()
    execute(monkeypatch, Recording(), job)
    *_, story = api
    path = renders / story.db.get(RenderJob, uuid.UUID(job["id"])).output_reference
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(PNG + b"tampered")
    response = image(api, job)
    assert response.status_code == 409 and response.json()["error"]["code"] == "RENDER_OUTPUT_UNAVAILABLE"
    assert str(path.name) not in response.text


def test_unfinished_failed_and_unstored_renders_have_no_image(api, monkeypatch, renders):
    original = stored(api)
    enable(monkeypatch, 2)
    queued = submit(api, original).json()
    assert image(api, queued).status_code == 409
    monkeypatch.setattr(render, "store", lambda data: (_ for _ in ()).throw(OSError("disk full")))
    unstored = submit(api, original, key="unstored").json()
    execute(monkeypatch, Recording(), unstored)
    view = current(api, unstored)
    assert (view["status"], view["error_code"]) == ("failed", "RENDER_STORAGE_FAILED")
    assert image(api, unstored).json()["error"]["code"] == "RENDER_OUTPUT_UNAVAILABLE"
    assert [item["status"] for item in history(api, original).json()["items"]] == ["failed", "queued"]
