"""Cache-scope matrix: a stored result answers only the exact scope and versions it was computed for."""

import threading

import pytest
from app.models.access import Principal
from app.models.visualizations import CachedResult, Visualization
from app.providers.deterministic import RuleAdapter
from app.services.narrative.entities import derive_entities
from app.services.reconstruction.cache import cache_key, lookup
from app.services.visualization import specification
from sqlalchemy import func, select
from tests.conftest import ORIGIN
from tests.test_appearance_states import annotated_consolidation
from tests.test_entity_extraction import fixture_adapter

pytestmark = pytest.mark.integration


class Counting(RuleAdapter):
    def __init__(self, model="rule-v1"):
        super().__init__(annotated_consolidation)
        self.model, self.calls = model, 0

    def complete(self, call):
        self.calls += 1
        return super().complete(call)


@pytest.fixture
def counted(api, monkeypatch):
    adapter = Counting()
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: adapter)
    compose, clients, work_id, story = api
    return compose, adapter, clients, work_id, story


def resolved(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "resolved", body
    return body["data"]


def test_the_same_scope_is_served_from_the_cache(counted):
    compose, adapter, _, _, story = counted
    first = resolved(compose(chapter=3, query="Arthur at home after the war"))
    calls = adapter.calls
    second = resolved(compose(chapter=3, query="Arthur at home after the war"))
    assert second == first and adapter.calls == calls
    assert story.db.scalar(select(func.count()).select_from(CachedResult)) == 1


def test_unparsed_query_words_are_inputs_to_cache_and_consolidation(counted):
    compose, adapter, _, _, _ = counted
    first = resolved(compose(chapter=3, query="Arthur at home after the war", context="at home",
                             moment={"kind": "phrase", "text": "after the war"}))
    calls = adapter.calls
    second = resolved(compose(chapter=3, query="Quietly, Arthur at home after the war", context="at home",
                              moment={"kind": "phrase", "text": "after the war"}))
    assert adapter.calls == calls + 1
    assert first["lineage"]["consolidation_id"] != second["lineage"]["consolidation_id"]


@pytest.mark.parametrize("change", [
    {"chapter": None},                                   # whole book never answers a chapter-limited reader
    {"chapter": 4},
    {"creative_mode": "interpretation"},
    {"style": "sepia ink wash"},
    {"query": "Arthur at home after the war with Mira"},
])
def test_any_change_of_scope_misses(counted, change):
    compose, adapter, _, _, story = counted
    base = {"chapter": 3, "query": "Arthur at home after the war"}
    resolved(compose(**base))
    before = story.db.scalar(select(func.count()).select_from(CachedResult))
    resolved(compose(**{**base, **change}))
    story.db.expire_all()
    assert story.db.scalar(select(func.count()).select_from(CachedResult)) == before + 1


def test_a_whole_book_entry_is_not_reused_at_a_cutoff(counted):
    compose, adapter, _, _, story = counted
    whole = resolved(compose(chapter=None, query="Arthur at home after the war"))
    limited = resolved(compose(chapter=4, query="Arthur at home after the war"))
    assert whole["scope"]["through_chapter_id"] is None and limited["scope"]["through_chapter_id"] is not None
    assert {t["attribute"] for t in limited["subject"]["traits"]} <= {t["attribute"] for t in whole["subject"]["traits"]}


def test_model_and_derivation_changes_recompute(counted, monkeypatch):
    compose, adapter, _, _, story = counted
    resolved(compose(chapter=3, query="Arthur at home after the war"))
    calls = adapter.calls
    newer = Counting("rule-v2")
    monkeypatch.setattr(specification, "consolidation_adapter", lambda: newer)
    resolved(compose(chapter=3, query="Arthur at home after the war"))
    assert newer.calls >= 1 and adapter.calls == calls
    # A new entity derivation (re-extraction with another model) is a new key as well.
    derive_entities(story.engine, story.generation, fixture_adapter("rule-v9"))
    before = newer.calls
    resolved(compose(chapter=3, query="Arthur at home after the war"))
    assert newer.calls == before + 1


def test_hits_never_cross_owners(counted):
    compose, adapter, clients, work_id, story = counted
    resolved(compose(chapter=3, query="Arthur at home after the war"))
    row = story.db.scalars(select(CachedResult)).one()
    assert row.key == cache_key(row.scope) and lookup(story.db, row.owner_id, row.scope) is not None
    other = story.db.scalar(select(Principal.id).where(Principal.id != row.owner_id))
    assert lookup(story.db, other, row.scope) is None
    assert compose(client="stranger", chapter=3, query="Arthur at home after the war").status_code == 404


def test_concurrent_creations_under_one_key_store_one_visualization(counted):
    compose, adapter, clients, work_id, story = counted
    from app.main import create_app
    from fastapi.testclient import TestClient
    results = []

    def create():
        with TestClient(create_app(), base_url="http://127.0.0.1") as client:
            client.post("/v1/auth/login", json={"username": "reader", "password": "synthetic query plan passphrase"},
                        headers=ORIGIN)
            results.append(client.post(f"/v1/works/{work_id}/visualizations", headers={
                **ORIGIN, "Idempotency-Key": "concurrent"}, json={
                "query": "Arthur at home after the war", "through_chapter_id": str(story.chapters[3])}))
    threads = [threading.Thread(target=create) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [r.status_code for r in results] == [201] * 4
    assert len({r.json()["visualization"]["id"] for r in results}) == 1
    story.db.expire_all()
    assert story.db.scalar(select(func.count()).select_from(Visualization)) == 1
    assert story.db.scalar(select(func.count()).select_from(CachedResult)) == 1
