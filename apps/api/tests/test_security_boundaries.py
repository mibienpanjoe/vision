"""Every HTTP route against anonymous, revoked, foreign-owner, cross-work and cross-origin callers."""

import json
import uuid
from contextlib import contextmanager

import pytest
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.test_refinement import ORIGIN, stored
from tests.test_render_contract import Recording, enable, execute, submit

pytestmark = pytest.mark.integration
PUBLIC = {("GET", "/health/live"), ("GET", "/health/ready"), ("GET", "/openapi.json"), ("POST", "/v1/auth/login")}
# Routes scoped to the caller rather than to an identifier in the path.
SELF = {("GET", "/v1/auth/me"), ("POST", "/v1/auth/logout"), ("GET", "/v1/works"), ("POST", "/v1/works"),
        ("POST", "/v1/jobs")}


@pytest.fixture
def world(api, monkeypatch, renders):
    """One of each owned resource for `reader`, including a stored private image."""
    _, clients, work_id, story = api
    view = stored(api)
    enable(monkeypatch, 2)
    job = submit(api, view).json()
    execute(monkeypatch, Recording(), job)
    reader = clients["reader"]
    works = reader.get("/v1/works").json()["items"]
    other = next(w["id"] for w in works if w["id"] != work_id)
    probe = reader.post("/v1/jobs", json={"value": 1}, headers={**ORIGIN, "Idempotency-Key": "probe"}).json()
    ingestion = story.db.execute(text(
        "SELECT j.id FROM ingestion_jobs j JOIN documents d ON d.id = j.document_id WHERE d.work_id = :w"),
        {"w": work_id}).scalar_one()
    spec = view["result"]["data"]
    span = spec["subject"]["traits"][0]["evidence"][0]
    boundary = {"mode": "through_chapter", "chapter_id": str(story.chapters[3])}
    ids = {"work_id": work_id, "visualization_id": view["id"], "job_id": job["id"],
           "entity_id": str(story.ids["Arthur"]), "number": "1"}
    bodies = {
        "/v1/jobs": {"value": 2},
        "/v1/works/{work_id}/evidence": {"span": span, "parser_revision": spec["scope"]["parser_revision"],
                                         "reading_boundary": boundary},
        "/v1/works/{work_id}/visualizations/compose": {"query": "Arthur", "through_chapter_id": boundary["chapter_id"]},
        "/v1/works/{work_id}/visualizations": {"query": "Arthur", "through_chapter_id": boundary["chapter_id"]},
        "/v1/works/{work_id}/visualizations/{visualization_id}/refinements": {
            "style": "charcoal", "creative_mode": "interpretation"},
        "/v1/works/{work_id}/visualizations/{visualization_id}/renders": {"specification_revision": 1},
        "/v1/works/{work_id}/renders/{job_id}/cancel": {},
    }
    return clients, story, ids, other, bodies, {"probe": probe["id"], "ingestion": str(ingestion)}


@contextmanager
def fresh():
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        yield client


def routes():
    # Included routers resolve lazily in this FastAPI; the generated contract lists every served operation.
    paths = create_app().openapi()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() for method in operations} | {
        ("GET", "/openapi.json")}


def fill(path, ids, extra):
    path = path.replace("/v1/jobs/{job_id}", f"/v1/jobs/{extra['probe']}")
    path = path.replace("ingestions/{job_id}", f"ingestions/{extra['ingestion']}").replace("{action}", "cancel")
    return path.format(**ids)


def call(client, method, template, ids, extra, bodies, headers=None, **body):
    headers = {**ORIGIN, "Idempotency-Key": "boundary", "If-Match": '"1"', **(headers or {})}
    if template == "/v1/works" and method == "POST":
        return client.post("/v1/works", data={"title": "x", "format": "md"}, files={"file": ("x.md", b"# One\n\nText.")},
                           headers={k: v for k, v in headers.items() if k != "If-Match"})
    payload = body.get("json", bodies.get(template))
    if method == "POST" and payload is None and "{action}" not in template and "generations" not in template:
        payload = {}
    return client.request(method, fill(template, ids, extra), headers=headers,
                          **({"json": payload} if payload is not None else {}))


def fingerprint(engine):
    """A digest of every application row, so a refused request is proven to have changed nothing."""
    with engine.connect() as connection:
        tables = connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                                         "AND tablename <> 'alembic_version' ORDER BY tablename")).all()
        return {t: connection.scalar(text(f'SELECT md5(coalesce(string_agg(r::text, \'|\' ORDER BY r::text), \'\')) '
                                          f'FROM "{t}" r')) for t in tables}


def denial(response):
    body = response.json()["error"]
    return response.status_code, body["code"], body["message"]


def test_route_inventory_is_covered_by_this_matrix():
    owned = {r for r in routes() if r not in PUBLIC | SELF}
    assert all("{work_id}" in path or path.startswith("/v1/jobs/") for _, path in owned), owned
    assert PUBLIC | SELF <= routes()


def test_anonymous_revoked_and_foreign_origin_callers_change_nothing(world, database):
    clients, story, ids, _, bodies, extra = world
    with fresh() as revoked, fresh() as anonymous:
        check_unauthenticated(clients, ids, extra, bodies, database, revoked, anonymous)


def check_unauthenticated(clients, ids, extra, bodies, database, revoked, anonymous):
    assert revoked.post("/v1/auth/login", json={"username": "reader", "password": "synthetic query plan passphrase"},
                        headers=ORIGIN).status_code == 200
    cookie = revoked.cookies.get("vision_session")
    assert revoked.post("/v1/auth/logout", headers=ORIGIN).status_code == 204
    revoked.cookies.set("vision_session", cookie)
    before = fingerprint(database)
    for method, template in sorted(routes() - PUBLIC):
        for caller in (anonymous, revoked):
            assert denial(call(caller, method, template, ids, extra, bodies)) == (
                401, "AUTHENTICATION_REQUIRED", "Authentication required."), (method, template)
        if method != "GET":
            for origin in ({"Origin": "http://evil.example"}, {"Origin": ""}):
                response = call(clients["reader"], method, template, ids, extra, bodies, headers=origin)
                assert denial(response)[:2] == (403, "ORIGIN_REJECTED"), (method, template)
    assert fingerprint(database) == before


def test_foreign_owner_and_cross_work_identifiers_are_indistinguishable_from_unknown_ones(world, database):
    clients, story, ids, other, bodies, extra = world
    unknown = {key: str(uuid.uuid4()) if key != "number" else "1" for key in ids}
    unknown_extra = {key: str(uuid.uuid4()) for key in extra}
    before = fingerprint(database)
    for method, template in sorted(routes() - PUBLIC - SELF):
        missing = denial(call(clients["stranger"], method, template, unknown, unknown_extra, bodies))
        assert missing[:2] == (404, "RESOURCE_NOT_FOUND"), (method, template, missing)
        assert denial(call(clients["stranger"], method, template, ids, extra, bodies)) == missing, (method, template)
        # Another work of the same owner never reaches a nested resource or another document's chapter.
        if template.count("{") > 1 or "ingestions" in template:
            elsewhere = denial(call(clients["reader"], method, template, {**unknown, "work_id": other},
                                    unknown_extra, bodies))
            assert elsewhere[0] in {404, 409}, (template, elsewhere)
            assert denial(call(clients["reader"], method, template, {**ids, "work_id": other},
                               extra, bodies)) == elsewhere, template
    stranger = clients["stranger"]
    assert stranger.get("/v1/auth/me").json()["username"] == "stranger"
    assert stranger.get("/v1/works").json()["items"] == []
    assert fingerprint(database) == before


def test_reading_boundaries_from_another_work_are_refused(world):
    clients, story, ids, other, bodies, extra = world
    with story.engine.connect() as connection:
        foreign = str(connection.scalar(text("SELECT id FROM chapters WHERE document_id = :d AND ordinal = 3"),
                                        {"d": story.other_document}))
    reader, work = clients["reader"], ids["work_id"]
    cutoff = {"through_chapter_id": foreign}
    attempts = [
        reader.get(f"/v1/works/{work}/entities", params=cutoff),
        reader.get(f"/v1/works/{work}/entities/{ids['entity_id']}", params=cutoff),
        reader.get(f"/v1/works/{work}/visualizations", params=cutoff),
        reader.get(f"/v1/works/{work}/visualizations/{ids['visualization_id']}", params=cutoff),
        reader.get(f"/v1/works/{work}/visualizations/{ids['visualization_id']}/revisions/1", params=cutoff),
        reader.post(f"/v1/works/{work}/visualizations/compose", json={"query": "Arthur", **cutoff}, headers=ORIGIN),
        reader.post(f"/v1/works/{work}/evidence", headers=ORIGIN, json={
            **bodies["/v1/works/{work_id}/evidence"], "reading_boundary": {"mode": "through_chapter",
                                                                            "chapter_id": foreign}}),
    ]
    for response in attempts:
        assert response.status_code in {404, 422}, (response.request.url, response.status_code, response.text)


def test_owner_responses_reach_resources_and_never_expose_storage(world, renders, tmp_path):
    clients, story, ids, other, bodies, extra = world
    leaks = [str(tmp_path), "source_ref", "output_ref", "password", "token_hash"]
    for method, template in sorted(routes() - PUBLIC - {("POST", "/v1/auth/logout"), ("DELETE", "/v1/works/{work_id}")}):
        response = call(clients["reader"], method, template, ids, extra, bodies)
        assert response.status_code not in {401, 403, 404, 500}, (method, template, response.text)
        if response.headers["content-type"].startswith("application/json"):
            dumped = json.dumps(response.json())
            assert not [leak for leak in leaks if leak in dumped], (method, template)
        assert not [leak for leak in leaks if leak in json.dumps(dict(response.headers))], (method, template)


def test_json_routes_bound_their_bodies_before_reading_them(world):
    clients, story, ids, _, bodies, extra = world
    padding = {"padding": "x" * 70_000}
    with fresh() as anonymous:
        for method, template in sorted(("POST", t) for t in [*bodies, "/v1/auth/login"]):
            for client in (anonymous, clients["reader"]):
                response = call(client, method, template, ids, extra, bodies, json=padding)
                assert response.status_code == 413, (method, template, response.status_code)
