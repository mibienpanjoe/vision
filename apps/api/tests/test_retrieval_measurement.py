"""Opt-in fusion-weight measurement on a public-domain novel through the real local pipeline.

Set VISION_MEASURE_NOVEL to the Project Gutenberg text of *Strange Case of Dr
Jekyll and Mr Hyde* (about 7 minutes on CPU). Results are written to
VISION_MEASURE_OUT (default `.local/measurements/fusion-jekyll.json`).
"""

import itertools
import json
import os
import pickle
import re
import time
from pathlib import Path

import pytest
from app.core.passwords import hash_password
from app.core.security import ActorScope
from app.main import create_app
from app.models.access import Principal
from app.models.generations import SourceGeneration
from app.models.passages import Passage
from app.providers.embeddings import LocalEmbeddings
from app.providers.local_entities import LocalEntities
from app.schemas.retrieval import VisualizationRequest
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.appearance import derive_appearance
from app.services.narrative.eligibility import visible_narrative
from app.services.narrative.entities import derive_entities
from app.services.narrative.pipeline import LIMITS
from app.services.retrieval.entity_lookup import SubjectLookup
from app.services.retrieval.evidence import collect
from app.services.retrieval.fusion import fuse
from app.services.retrieval.fusion import select as budgeted
from app.services.retrieval.lexical import (
    appearance_linked,
    entity_linked,
    lexical,
    passage_infos,
    terms,
)
from app.services.retrieval.query_plan import QueryPlan, plan_query
from app.services.retrieval.semantic import index_passages, semantic
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not os.environ.get("VISION_MEASURE_NOVEL"), reason="Set VISION_MEASURE_NOVEL to the Gutenberg Jekyll text")]
ORIGIN = {"Origin": "http://127.0.0.1:3000"}
HEADINGS = ["STORY OF THE DOOR", "SEARCH FOR MR. HYDE", "DR. JEKYLL WAS QUITE AT EASE", "THE CAREW MURDER CASE",
            "INCIDENT OF THE LETTER", "INCIDENT OF DR. LANYON", "INCIDENT AT THE WINDOW", "THE LAST NIGHT",
            "DR. LANYON’S NARRATIVE", "HENRY JEKYLL’S FULL STATEMENT OF THE CASE"]
# Query -> distinctive phrases identifying the gold passages (the research spike's set, 2026-10-21).
QUERIES = {
    "What does Mr Hyde look like?": ["dwarfish", "deformity", "deformed"],
    "Utterson the lawyer's face and appearance": ["rugged countenance"],
    "Dr Jekyll's hand compared with Hyde's hand": ["corded, knuckly", "comely"],
    "the door and the building in the by-street": ["blistered and distained", "sinister block of building"],
    "Dr Jekyll's age, build and face": ["smooth-faced man of fifty"],
    "What did Dr Lanyon look like before his shock?": ["dapper, red-faced", "shock of hair prematurely white"],
    "How had Lanyon's looks changed when he was dying?": ["death-warrant written legibly", "rosy man had grown pale"],
    "the elderly victim walking in the moonlit lane": ["beautiful gentleman with white hair",
                                                       "brilliantly lit by the full moon"],
    "the weapon used to kill Sir Danvers Carew": ["very tough and heavy wood"],
    "colour of the fog over London that morning": ["chocolate-coloured pall"],
    "the Soho street where Hyde lived": ["dismal quarter of Soho", "gin palace"],
    "how Hyde's rooms were decorated inside": ["furnished with luxury"],
    "the old woman who opened Hyde's door": ["ivory-faced and silvery-haired"],
    "furniture in Dr Jekyll's private cabinet": ["glass presses", "cheval-glass"],
    "the old laboratory building behind the doctor's house": ["dissecting rooms", "dingy, windowless structure"],
    "the entrance hall of Jekyll's house": ["costly cabinets of oak", "bright, open fire"],
    "the square where Jekyll's house stands": ["square of ancient, handsome houses"],
    "how Hyde's borrowed clothes fitted him at Lanyon's": ["enormously too large", "waist of the coat below his haunches"],
    "colour changes of the potion while mixing": ["reddish hue"],
    "the powder kept in the drawer": ["crystalline salt"],
    "the dead man found on the cabinet floor": ["sorely contorted", "clothes far too large"],
    "the sky and weather on the last night": ["pale moon"],
    "Dr Jekyll sitting at the window looking sad": ["disconsolate prisoner"],
    "the covered door at the top of the stairs": ["red baize"],
    "the face covering Poole saw on his master": ["mask upon his face", "that thing in the mask"],
}
GRID = {"lexical": [0, 0.25, 0.5, 1], "entity": [0, 0.1, 0.25, 0.5], "appearance": [0, 0.25, 0.5, 1]}


def markdown(raw: str) -> str:
    body = raw.split("*** START OF THE PROJECT GUTENBERG EBOOK", 1)[1].split("***", 1)[1]
    body = body.split("*** END OF THE PROJECT GUTENBERG EBOOK", 1)[0]
    out, chapter = ["# Strange Case of Dr Jekyll and Mr Hyde"], 0
    for block in re.split(r"\n\s*\n", body):
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if text in HEADINGS:
            chapter = HEADINGS.index(text) + 1
            out.append(f"## Chapter {chapter} — {text.title()}")
        elif chapter and len(text) > 20:
            out.append(text)
    return "\n\n".join(out) + "\n"


def recall(order, gold, k):
    return len(set(order[:k]) & gold) / len(gold)


def test_measure_fusion_weights_on_a_novel(database, monkeypatch, tmp_path):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(tmp_path / "originals"))
    source = markdown(Path(os.environ["VISION_MEASURE_NOVEL"]).read_text(encoding="utf-8"))
    with Session(database) as db:
        db.add(Principal(username="measure", password_hash=hash_password("synthetic measurement passphrase")))
        db.commit()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/auth/login", json={"username": "measure", "password": "synthetic measurement passphrase"},
                           headers=ORIGIN).status_code == 200
        accepted = client.post("/v1/works", data={"title": "Jekyll", "format": "md"},
                               files={"file": ("jekyll.md", source.encode())},
                               headers={**ORIGIN, "Idempotency-Key": "measure-novel"}).json()
        execute_ingestion(accepted["job"]["id"])
        generation = client.get(f"/v1/works/{accepted['work']['id']}/generations").json()["items"][0]["id"]
    timings = {}
    started = time.monotonic()
    entities = derive_entities(database, generation, LocalEntities(), LIMITS)
    derive_appearance(database, generation, entities)
    timings["entities_appearance_s"] = round(time.monotonic() - started, 1)
    embedder = LocalEmbeddings()
    started = time.monotonic()
    index_passages(database, generation, embedder)
    timings["index_s"] = round(time.monotonic() - started, 1)

    paths, unresolved = [], {}
    with Session(database) as db:
        actor = ActorScope(db.scalar(select(Principal.id)), "measure")
        texts = dict(db.execute(select(Passage.id, Passage.text).where(
            Passage.document_id == accepted["work"]["document_id"])).all())
        for query, phrases in QUERIES.items():
            plan = plan_query(db, actor, accepted["work"]["id"],
                              VisualizationRequest.model_validate_json(json.dumps({"query": query})))
            if not isinstance(plan, QueryPlan):
                unresolved[query] = type(plan).__name__
                continue
            view = visible_narrative(db, db.get(SourceGeneration, plan.generation_id), plan.cutoff)
            names = SubjectLookup(view).names(plan.subject)
            found = collect(entity_linked(db, plan, view), appearance_linked(db, plan, view),
                            lexical(db, plan, names, terms(plan)), semantic(db, plan, embedder))
            gold = {pid for pid, text in texts.items() if any(p in text for p in phrases)}
            paths.append((query, plan.subject.label, found, gold, passage_infos(db, plan)))

    def score(weights):
        """recall@5/10/20 of the fused order, and recall of the budgeted selection actually sent onward."""
        rows = []
        for _, _, found, gold, infos in paths:
            ranked = fuse(found, weights)
            order = [r.passage_id for r in ranked]
            chosen = [s.passage_id for s in budgeted(ranked, infos).passages]
            rows.append([recall(order, gold, 5), recall(order, gold, 10), recall(order, gold, 20),
                         recall(chosen, gold, len(chosen))])
        return {name: round(sum(r[i] for r in rows) / len(rows), 3)
                for i, name in enumerate(("recall@5", "recall@10", "recall@20", "selection"))}

    grid = []
    for lexical_w, entity_w, appearance_w in itertools.product(*GRID.values()):
        weights = {"semantic": 1.0, "lexical": lexical_w, "entity": entity_w, "appearance": appearance_w}
        grid.append({"weights": weights, **score(weights)})
    grid.sort(key=lambda g: (-g["selection"], -g["recall@10"], -g["recall@5"], sum(g["weights"].values())))
    baselines = {name: score(w) for name, w in {
        "semantic_only": {"semantic": 1.0},
        "lexical_only": {"lexical": 1.0},
        "equal_rrf": {"semantic": 1.0, "lexical": 1.0, "entity": 1.0, "appearance": 1.0}}.items()}
    result = {"passages": len(texts), "queries": len(QUERIES), "resolved": len(paths), "unresolved": unresolved,
              "subjects": {q: label for q, label, *_ in paths}, **timings, "baselines": baselines,
              "best": grid[:10], "grid": grid}
    out = Path(os.environ.get("VISION_MEASURE_OUT", Path(__file__).parents[3] / ".local/measurements/fusion-jekyll.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    # Candidates and gold sets for offline re-scoring of selection rules (local, ignored data).
    out.with_suffix(".pkl").write_bytes(pickle.dumps([(q, label, found, gold, infos) for q, label, found, gold, infos
                                                      in paths]))
    print(json.dumps({k: v for k, v in result.items() if k != "grid"}, indent=2, ensure_ascii=False))
    assert grid[0]["selection"] >= baselines["semantic_only"]["selection"]
