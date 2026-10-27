"""Context-budget exhaustion through the real compose path: protected evidence never disappears silently."""

import json
import os
import re
import resource
import time
import uuid
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.main import create_app
from app.models.access import Principal
from app.models.entities import Entity
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation, ModelRun
from app.models.narrative_jobs import NarrativeJob
from app.models.passages import Passage
from app.models.works import Document
from app.services.ingestion.parse import execute_ingestion
from app.services.retrieval import fusion
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session
from tests.conftest import ORIGIN, visualization_request

pytestmark = pytest.mark.integration


def compose_with(api, monkeypatch, budget, **body):
    compose, *_ = api
    monkeypatch.setenv("VISION_CONTEXT_PASSAGES", str(budget.passages))
    monkeypatch.setenv("VISION_CONTEXT_CHARACTERS", str(budget.characters))
    response = compose(chapter=3, query="Arthur at dinner with Mira", **body)
    assert response.status_code == 200, response.text
    return response.json()


def test_default_budget_selects_the_synthetic_scene_without_overflow(api, monkeypatch):
    result = compose_with(api, monkeypatch, fusion.Budget())
    assert result["outcome"] == "resolved"
    assert result["data"]["verification"]["selection"] in {"complete", "truncated"}


@pytest.mark.parametrize("characters", [60, 200, 350])
def test_a_cap_below_the_needed_sentences_is_an_explicit_outcome(api, monkeypatch, characters):
    # The synthetic dinner needs more than 400 characters of protected and event sentences; below that the moment
    # is lost and the answer says so instead of resolving without it. A resolved overflow is labelled
    # protected_overflow (test_fusion) and shown in the workspace.
    result = compose_with(api, monkeypatch, fusion.Budget(passages=3, characters=characters))
    assert result["outcome"] == "insufficient_evidence", result


def test_a_tight_cap_keeps_protected_sentences_while_dropping_passages(api, monkeypatch):
    result = compose_with(api, monkeypatch, fusion.Budget(passages=2, characters=1500))
    assert result["outcome"] == "resolved", result
    assert result["data"]["verification"]["selection"] == "truncated"
    assert {t["attribute"] for t in result["data"]["subject"]["traits"]} == {"attire", "left_cheek"}


def test_a_changed_budget_is_a_different_cache_key(api, monkeypatch):
    assert compose_with(api, monkeypatch, fusion.Budget(passages=3, characters=20_000))["outcome"] == "resolved"
    # A result computed under a larger budget is not served once the cap is recalibrated below its needs.
    assert compose_with(api, monkeypatch, fusion.Budget(passages=3, characters=400))["outcome"] == "insufficient_evidence"


@pytest.mark.parametrize("limit", ["passages", "characters"])
def test_backward_context_cannot_exceed_the_configured_provider_budget(api, monkeypatch, limit):
    from app.providers.deterministic import RuleAdapter
    from app.services.retrieval.evidence import Candidate
    from app.services.visualization import specification

    _, _, _, story = api
    document = story.db.get(SourceGeneration, story.generation).document_id
    passage = story.db.scalar(select(Passage).where(Passage.document_id == document,
                                                   Passage.chapter_ordinal <= 3).order_by(Passage.ordinal.desc()))
    assert passage.ordinal > 1
    # A single unanchored hit needs its previous passage for attribution. Both configured caps must
    # constrain the actual provider input, including that backward context.
    monkeypatch.setattr(specification, "collect", lambda *paths: [
        Candidate(passage.id, 0, len(passage.text), {"semantic": 1})])
    sent = []

    def response(sources):
        sent.extend(s for s in sources if s["ref"] != "request")
        return {"events": [], "facts": [], "identity_links": []}

    monkeypatch.setattr(specification, "consolidation_adapter", lambda: RuleAdapter(response))
    budget = fusion.Budget(passages=1 if limit == "passages" else 20,
                           characters=len(passage.text) if limit == "characters" else 20_000)
    compose_with(api, monkeypatch, budget)
    assert sent
    assert len(sent) <= budget.passages
    assert sum(len(s["text"]) for s in sent) <= budget.characters


# Opt-in book-length measurement (T44). VISION_MEASURE_BOOKS names a directory holding the Project Gutenberg
# texts jekyll.txt (#43) and pride.txt (#1342). Local models run on CPU (about an hour); with GROQ_API_KEY set,
# five public-domain composes per book also call the live consolidation/adjudication model.
PRIDE_QUERIES = {
    "Mr Darcy's appearance at the ball": ["fine, tall person, handsome features, noble mien"],
    "Mr Bingley's looks and manner": ["pleasant countenance"],
    "Mr Collins's looks when he arrived": ["tall, heavy-looking young man"],
    "Elizabeth's eyes": ["pair of fine eyes"],
    "Elizabeth's petticoat after walking to Netherfield": ["six inches deep in mud"],
    "Lady Catherine de Bourgh's appearance": ["tall, large woman", "strongly-marked features"],
    "Miss de Bourgh's looks": ["pale and sickly"],
    "Mr Wickham's appearance": ["appearance was greatly in his favour"],
    "Pemberley house seen from the road": ["large, handsome stone building"],
}
LIVE = {"jekyll": ["What does Mr Hyde look like?", "Utterson the lawyer's face and appearance",
                   "the door and the building in the by-street", "the old laboratory building behind the doctor's house",
                   "how Hyde's borrowed clothes fitted him at Lanyon's"],
        "pride": ["Mr Darcy's appearance at the ball", "Mr Collins's looks when he arrived",
                  "Pemberley house seen from the road", "Elizabeth's petticoat after walking to Netherfield",
                  "Lady Catherine de Bourgh's appearance"]}
PRIDE_HEADING = re.compile(r"^\s*chapter ([ivxlc]+)\.?\]?\s*$", re.IGNORECASE)


def pride_markdown(raw: str) -> str:
    body = raw.split("*** START OF THE PROJECT GUTENBERG EBOOK", 1)[1].split("***", 1)[1]
    body = body.split("*** END OF THE PROJECT GUTENBERG EBOOK", 1)[0]
    out, chapter = ["# Pride and Prejudice"], 0
    for block in re.split(r"\n\s*\n", body.replace("\r", "")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if any(PRIDE_HEADING.match(line) for line in lines):
            chapter += 1
            out.append(f"## Chapter {chapter}")
        elif chapter and lines and not lines[0].startswith("[Illustration"):
            text = " ".join(lines)
            if len(text) > 20:
                out.append(text)
    return "\n\n".join(out) + "\n"


def explain(engine, statements):
    """EXPLAIN ANALYZE for captured retrieval SQL: execution time and any sequential scan of a large table."""
    plans = []
    with engine.connect() as connection:
        raw = connection.connection.dbapi_connection
        for statement, parameters in statements:
            with raw.cursor() as cursor:
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters)
                plan = cursor.fetchone()[0][0]
            nodes, stack = [], [plan["Plan"]]
            while stack:
                node = stack.pop()
                nodes.append(f'{node["Node Type"]}:{node.get("Relation Name", node.get("Index Name", ""))}')
                stack.extend(node.get("Plans", []))
            plans.append({"kind": "semantic" if "<=>" in statement else "lexical", "execution_ms": plan["Execution Time"], "nodes": sorted(set(nodes))})
        raw.rollback()
    return plans


@pytest.mark.skipif(not os.environ.get("VISION_MEASURE_BOOKS"), reason="Set VISION_MEASURE_BOOKS to the corpus directory")
def test_measure_book_length_budgets(database, monkeypatch, tmp_path):
    from app.providers.embeddings import LocalEmbeddings
    from app.services.narrative.pipeline import execute_narrative
    from app.services.retrieval.semantic import semantic
    from tests.test_retrieval_measurement import QUERIES, markdown

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    monkeypatch.setenv("VISION_NARRATIVE_PROVIDER", "local")
    corpus = Path(os.environ["VISION_MEASURE_BOOKS"])
    books = {"jekyll": (markdown, QUERIES), "pride": (pride_markdown, PRIDE_QUERIES)}
    only = os.environ.get("VISION_MEASURE_ONLY")  # one book per process bounds peak memory on small machines
    books = {name: (convert((corpus / f"{name}.txt").read_text(encoding="utf-8")), queries)
             for name, (convert, queries) in books.items() if only in (None, name)}
    with Session(database) as db:
        db.add(Principal(username="measure", password_hash=hash_password("synthetic measurement passphrase")))
        db.commit()
    budget, embedder, results = fusion.configured_budget(), LocalEmbeddings(), {}
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "measure", "password": "synthetic measurement passphrase"},
                           headers=ORIGIN).status_code == 200
        for name, (source, queries) in books.items():
            row = results[name] = {"characters": len(source), "words": len(source.split())}
            accepted = client.post("/v1/works", data={"title": name, "format": "md"},
                                   files={"file": (f"{name}.md", source.encode())},
                                   headers={**ORIGIN, "Idempotency-Key": f"measure-{name}"}).json()
            work_id, started = accepted["work"]["id"], time.monotonic()
            execute_ingestion(accepted["job"]["id"])
            row["parse_s"] = round(time.monotonic() - started, 1)
            with Session(database) as db:
                generation = db.scalar(select(SourceGeneration.id).where(
                    SourceGeneration.document_id == uuid.UUID(accepted["work"]["document_id"])))
                narrative = db.scalar(select(NarrativeJob.id).where(NarrativeJob.generation_id == generation))
                row["passages"] = db.scalar(select(func.count()).select_from(Passage).where(
                    Passage.document_id == uuid.UUID(accepted["work"]["document_id"])))
            started = time.monotonic()
            execute_narrative(str(narrative))
            row["narrative_s"] = round(time.monotonic() - started, 1)
            with Session(database) as db:
                job = db.get(NarrativeJob, narrative)
                row["narrative_status"] = job.status
                row["stages_s"] = {d.stage: round((d.completed_at - d.created_at).total_seconds(), 1)
                                   for d in db.scalars(select(Derivation).where(Derivation.generation_id == generation))
                                   if d.completed_at}
                row["entities"] = db.scalar(select(func.count()).select_from(Entity).join(
                    Derivation, Derivation.id == Entity.derivation_id).where(Derivation.generation_id == generation))
            row["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
            row["queries"] = measure_queries(database, work_id, queries, embedder, budget, semantic)
            row["live"] = live_composes(client, database, work_id, LIVE[name]) if os.environ.get("GROQ_API_KEY") else []
            out = Path(os.environ.get("VISION_MEASURE_OUT",
                                      Path(__file__).parents[3] / f".local/measurements/budgets-{only or 'all'}.json"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"budget": [budget.passages, budget.characters], "books": results}, indent=2,
                                      ensure_ascii=False, default=str))
    for row in results.values():
        assert row["narrative_status"] == "succeeded"
        # A cap may leave protected evidence out, but never silently.
        assert all(q["selection"] == "protected_overflow" for q in row["queries"] if q.get("protected_omitted"))
    if keep := os.environ.get("VISION_MEASURE_KEEP_DB"):  # a processed copy for offline profiling (local only)
        name = database.url.database
        database.dispose()
        admin = create_engine(database.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                    "WHERE datname = :name AND pid <> pg_backend_pid()"), {"name": name})
            connection.execute(text(f'CREATE DATABASE "{keep}" TEMPLATE "{name}"'))
        admin.dispose()


def measure_queries(engine, work_id, queries, embedder, budget, semantic):
    from app.core.security import ActorScope
    from app.services.narrative.eligibility import visible_narrative
    from app.services.retrieval.entity_lookup import SubjectLookup
    from app.services.retrieval.evidence import collect
    from app.services.retrieval.lexical import (
        appearance_linked,
        entity_linked,
        lexical,
        passage_infos,
        terms,
    )
    from app.services.retrieval.query_plan import QueryPlan, plan_query

    rows, captured = [], []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "passage" in statement and ("<=>" in statement or "tsquery" in statement):
            captured.append((statement, parameters))

    with Session(engine) as db:
        actor = ActorScope(db.scalar(select(Principal.id)), "measure")
        texts = dict(db.execute(select(Passage.id, Passage.text).join(Document, Document.id == Passage.document_id)
                                .where(Document.work_id == uuid.UUID(work_id))).all())
        for query, phrases in queries.items():
            started = time.monotonic()
            plan = plan_query(db, actor, uuid.UUID(work_id), visualization_request(query=query))
            if not isinstance(plan, QueryPlan):
                rows.append({"query": query, "plan": type(plan).__name__})
                continue
            event.listen(engine, "before_cursor_execute", capture)
            try:
                view = visible_narrative(db, db.get(SourceGeneration, plan.generation_id), plan.cutoff)
                paths = [entity_linked(db, plan, view), appearance_linked(db, plan, view),
                         lexical(db, plan, SubjectLookup(view).names(plan.subject), terms(plan)),
                         semantic(db, plan, embedder) or []]
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            ranked = fusion.fuse(collect(*paths))
            selection = fusion.select(ranked, passage_infos(db, plan), budget)
            gold = {pid for pid, text in texts.items() if any(p in text for p in phrases)}
            chosen = {s.passage_id for s in selection.passages}
            rows.append({"query": query, "subject": plan.subject.label,
                         "retrieval_ms": round((time.monotonic() - started) * 1000),
                         "candidates": [len(p) for p in paths], "ranked": len(ranked),
                         "selection": selection.outcome, "sent_passages": len(chosen),
                         "sent_characters": sum(e - s for p in selection.passages for s, e in p.spans),
                         "protected_omitted": selection.protected_omitted, "omitted": selection.omitted,
                         "gold": len(gold), "gold_selected": len(gold & chosen)})
    kinds = {"lexical": "tsquery", "semantic": "<=>"}
    chosen_sql = [next(c for c in captured if marker in c[0]) for marker in kinds.values()
                  if any(marker in c[0] for c in captured)]
    rows.append({"explain": explain(engine, chosen_sql)})
    return rows


def live_composes(client, engine, work_id, queries):
    rows = []
    for index, query in enumerate(queries):
        if index:
            time.sleep(65)  # one consolidation is ~6k input tokens; the free Groq tier allows about one per minute
        with Session(engine) as db:
            before = db.scalar(select(func.count()).select_from(ModelRun))
        started = time.monotonic()
        response = client.post(f"/v1/works/{work_id}/visualizations/compose", json={"query": query}, headers=ORIGIN)
        elapsed = round(time.monotonic() - started, 1)
        with Session(engine) as db:
            runs = db.scalars(select(ModelRun).order_by(ModelRun.started_at).offset(before)).all()
        body = response.json()
        rows.append({"query": query, "status": response.status_code, "outcome": body.get("outcome"),
                     "error": (body.get("error") or {}).get("code"), "seconds": elapsed,
                     "selection": body.get("data", {}).get("verification", {}).get("selection"),
                     "traits": sorted(t["attribute"] for t in body.get("data", {}).get("subject", {}).get("traits", [])),
                     "runs": [{"purpose": r.purpose, "model": r.model, "outcome": r.outcome, "in": r.input_tokens,
                               "out": r.output_tokens, "ms": r.duration_ms} for r in runs]})
    return rows
