import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from app.models.entities import EntityRelation
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation, ModelRun
from app.models.passages import Passage
from app.models.visual_facts import FactEvidence, VisualFact
from app.providers.contracts import (
    ProviderCall,
    ProviderInputTooLarge,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.providers.deterministic import RuleAdapter, ScriptedAdapter
from app.providers.openai_compatible import GroqGateway
from app.services.narrative.eligibility import visible_narrative
from app.services.retrieval.consolidation import consolidate
from app.services.retrieval.entity_lookup import SubjectLookup
from app.services.retrieval.evidence import collect
from app.services.retrieval.fusion import Budget, Selected, Selection, fuse, select
from app.services.retrieval.lexical import (
    appearance_linked,
    entity_linked,
    lexical,
    passage_infos,
    terms,
)
from app.services.retrieval.rerank import Expanded, expand
from sqlalchemy import func
from sqlalchemy import select as query

INJURY = "Ten years later, during the war, a blade cut Arthur's left cheek and left a scar."
REMOVAL = "Before dinner, Arthur removed his steel armor and put on a plain linen shirt."
RUMOR = "People claim Arthur has golden eyes, but I have never seen them."


def consolidation_rule(sources):
    """An 'ideal model' over whatever excerpts it is given, plus hostile and mistaken items."""
    text = {s["ref"]: s["text"] for s in sources if s["ref"] != "request"}

    def ref(quote):
        return next((r for r, t in text.items() if quote in t), None)

    events, facts, links = [], [], []
    if ref(INJURY):
        events.append({"key": "war", "label": "the war", "modality": "fact", "participants": ["Arthur"],
                       "evidence": [{"ref": ref(INJURY), "quote": INJURY}]})
        facts += [
            {"subject": "Arthur", "attribute": "left_cheek", "value": "scar", "kind": "acquired", "support": "explicit",
             "modality": "fact", "events": ["war"], "evidence": [{"ref": ref(INJURY), "quote": INJURY}]},
            {"subject": "Arthur", "attribute": "held_object", "value": "silver sword", "kind": "scene",
             "support": "explicit", "modality": "fact", "events": ["war"],
             "evidence": [{"ref": ref(INJURY), "quote": "Brann, not Arthur, held the silver sword."}]},
            {"subject": "Arthur", "attribute": "eyes", "value": "violet", "kind": "identity", "support": "explicit",
             "modality": "fact", "evidence": [{"ref": ref(INJURY), "quote": "Arthur had violet eyes."}]},
        ]
    if ref(REMOVAL):
        events.append({"key": "dinner", "label": "dinner at home", "modality": "fact", "participants": ["Arthur"],
                       "evidence": [{"ref": ref(REMOVAL), "quote": REMOVAL}]})
        for value in ("steel armor", "plain linen shirt"):  # the armor claim ignores the removal
            facts.append({"subject": "Arthur", "attribute": "attire", "value": value, "kind": "scene",
                          "support": "explicit", "modality": "fact", "events": ["dinner"],
                          "evidence": [{"ref": ref(REMOVAL), "quote": REMOVAL}]})
    if ref(RUMOR):
        facts.append({"subject": "Arthur", "attribute": "eyes", "value": "golden", "kind": "identity",
                      "support": "explicit", "modality": "fact", "evidence": [{"ref": ref(RUMOR), "quote": RUMOR}]})
    if ref("I was Wren at ten"):
        links.append({"subject": "Wren", "object": "Arthur", "support": "explicit", "ref": ref("I was Wren at ten"),
                      "quote": "Only this chapter established that Wren and Arthur were the same person."})
    return {"events": events, "facts": facts, "identity_links": links}


def gathered(story, cutoff, query_text, budget=Budget()):
    plan = story.plan(cutoff, query=query_text)
    view = visible_narrative(story.db, story.db.get(SourceGeneration, plan.generation_id), plan.cutoff)
    found = collect(entity_linked(story.db, plan, view), appearance_linked(story.db, plan, view),
                    lexical(story.db, plan, SubjectLookup(view).names(plan.subject), terms(plan)))
    infos = passage_infos(story.db, plan)
    anchors = {c.passage_id: c.anchors for c in found if c.anchors}
    return plan, expand(select(fuse(found), infos, budget), infos, anchors, budget), infos


def counts(story, model):
    story.db.expire_all()
    return story.db.scalar(query(func.count()).select_from(model))


@pytest.mark.integration
def test_consolidation_publishes_only_gated_facts_from_in_scope_passages(story):
    plan, expanded, infos = gathered(story, 2, "Arthur during the war")
    assert {story.db.get(Passage, s.passage_id).chapter_ordinal for s in expanded.selection.passages} <= {1, 2}
    adapter = RuleAdapter(consolidation_rule)
    derivation_id = consolidate(story.engine, plan, expanded, adapter)
    story.db.expire_all()
    derivation = story.db.get(Derivation, derivation_id)
    assert (derivation.stage, derivation.status, derivation.scope["cutoff"]) == ("consolidation", "succeeded", 2)
    assert derivation.rejections == {"wrong_owner": 1, "ungrounded": 1, "speculative": 1}
    facts = story.db.scalars(query(VisualFact).where(VisualFact.derivation_id == derivation_id)).all()
    assert [(f.attribute, f.value, f.canonical) for f in facts] == [("left_cheek", "scar", True)]
    evidence = story.db.scalars(query(FactEvidence).where(FactEvidence.fact_id == facts[0].id)).all()
    passage = story.db.get(Passage, evidence[0].passage_id)
    assert passage.text[evidence[0].start:evidence[0].end] == INJURY
    run = story.db.scalar(query(ModelRun).where(ModelRun.derivation_id == derivation_id))
    sent = {int(ref[1:]) for ref in run.input_refs if ref != "request"}
    assert sent and all(infos[p].ordinal in sent for p in [s.passage_id for s in expanded.selection.passages])
    assert {p.chapter_ordinal for p in story.db.scalars(query(Passage).where(
        Passage.document_id == plan.document_id, Passage.ordinal.in_(sent)))} <= {1, 2}

    runs = counts(story, ModelRun)
    assert consolidate(story.engine, plan, expanded, adapter) == derivation_id  # same scope reuses
    assert counts(story, ModelRun) == runs
    later, later_expanded, _ = gathered(story, 3, "Arthur during the war")
    assert consolidate(story.engine, later, later_expanded, adapter) != derivation_id


@pytest.mark.integration
def test_removed_attire_and_hedged_colour_never_become_canonical(story):
    plan, expanded, _ = gathered(story, 3, "Arthur at home after the war")
    derivation_id = consolidate(story.engine, plan, expanded, RuleAdapter(consolidation_rule))
    story.db.expire_all()
    rejections = story.db.get(Derivation, derivation_id).rejections
    assert rejections["negated_or_question"] == 1 and rejections["speculative"] == 1
    facts = story.db.scalars(query(VisualFact).where(VisualFact.derivation_id == derivation_id)).all()
    assert ("attire", "plain linen shirt", True) in [(f.attribute, f.value, f.canonical) for f in facts]
    assert not any(f.value in {"steel armor", "golden"} for f in facts)


@pytest.mark.integration
def test_provider_failure_is_recorded_and_never_falls_back(story):
    plan, expanded, _ = gathered(story, 2, "Arthur during the war")
    failing = ScriptedAdapter(ProviderRateLimited(), json.dumps(consolidation_rule([])))
    first = consolidate(story.engine, plan, expanded, failing)
    story.db.expire_all()
    derivation = story.db.get(Derivation, first)
    assert (derivation.status, derivation.error_code) == ("failed", "PROVIDER_RATE_LIMITED")
    assert counts(story, VisualFact) == 0
    assert consolidate(story.engine, plan, expanded, failing) == first  # retried claim, empty answer this time
    story.db.expire_all()
    assert (story.db.get(Derivation, first).status, story.db.get(Derivation, first).attempt) == ("succeeded", 2)


@pytest.mark.integration
def test_one_malformed_answer_gets_one_more_call(story):
    plan, expanded, _ = gathered(story, 2, "Arthur during the war")
    adapter = ScriptedAdapter('{"facts": [{"subject": "Arthur"}]}', json.dumps(consolidation_rule([])))
    derivation_id = consolidate(story.engine, plan, expanded, adapter)
    story.db.expire_all()
    assert story.db.get(Derivation, derivation_id).status == "succeeded" and len(adapter.calls) == 2
    outcomes = [r.outcome for r in story.db.scalars(query(ModelRun).where(ModelRun.derivation_id == derivation_id)
                                                    .order_by(ModelRun.started_at))]
    assert outcomes == ["invalid_output", "succeeded"]
    twice = ScriptedAdapter("not json", "still not json", "never called")
    later, later_expanded, _ = gathered(story, 3, "Arthur during the war")
    failed = consolidate(story.engine, later, later_expanded, twice)
    story.db.expire_all()
    assert (story.db.get(Derivation, failed).error_code, len(twice.calls)) == ("PROVIDER_INVALID_OUTPUT", 2)


@pytest.mark.integration
def test_input_outside_the_boundary_is_refused_and_links_stay_scoped(story):
    plan, expanded, infos = gathered(story, 2, "Arthur during the war")
    late = next(pid for pid, info in passage_infos(story.db, story.plan(None, query="Arthur")).items()
                if "I was Wren" in info.text)
    leaked = Expanded(Selection([Selected(late, [(0, 10)], {}, [], False)], "complete", 0, 0, []), [], 0)
    with pytest.raises(ValueError):
        consolidate(story.engine, plan, leaked, RuleAdapter(consolidation_rule))

    whole, whole_expanded, _ = gathered(story, None, "Wren at ten", Budget(passages=40, characters=40_000))
    before = counts(story, EntityRelation)
    derivation_id = consolidate(story.engine, whole, whole_expanded, RuleAdapter(consolidation_rule))
    story.db.expire_all()
    links = story.db.scalars(query(EntityRelation).where(EntityRelation.derivation_id == derivation_id)).all()
    assert [link.relation for link in links] == ["same_as"] and counts(story, EntityRelation) == before + 1


def test_expansion_adds_only_earlier_context_and_reports_budget_refusals():
    from app.services.retrieval.fusion import PassageInfo
    ids = [uuid.uuid4() for _ in range(3)]
    infos = {ids[0]: PassageInfo(0, "Arthur came home."), ids[1]: PassageInfo(1, "He wore a linen shirt."),
             ids[2]: PassageInfo(2, "Arthur smiled at dinner.")}
    selection = Selection([Selected(ids[1], [(0, 22)], {"semantic": 1}, [(0, 22)], False),
                           Selected(ids[2], [(0, 24)], {"entity": 1}, [], False)], "complete", 0, 0, [])
    anchors = {ids[2]: {(0, 6)}}
    expanded = expand(selection, infos, anchors)
    assert (expanded.context, expanded.unexpanded) == ([ids[0]], 0)
    tight = expand(selection, infos, anchors, Budget(characters=50))
    assert (tight.context, tight.unexpanded) == ([], 1)


class Groq(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        status, payload, headers = self.server.replies.pop(0)
        data = json.dumps(payload).encode()
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def groq():
    server = HTTPServer(("127.0.0.1", 0), Groq)
    server.seen, server.replies = [], []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


def call(timeout=5):
    return ProviderCall(system="sys", data='{"sources": []}', output_schema={"type": "object"},
                        max_output_tokens=64, timeout_seconds=timeout)


def test_groq_adapter_honours_retry_after_once_and_sends_the_schema(groq):
    adapter = GroqGateway(f"http://127.0.0.1:{groq.server_port}/openai/v1", "gsk-synthetic", "openai/gpt-oss-120b")
    ok = (200, {"model": "openai/gpt-oss-120b", "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                "choices": [{"message": {"content": "{}"}}]}, {})
    limited = (429, {"error": {"message": "rate limit"}}, {"retry-after": "1"})
    groq.replies = [limited, ok]
    started = time.monotonic()
    assert adapter.complete(call()).output == "{}" and time.monotonic() - started >= 1
    assert groq.seen[0]["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "output", "schema": {"type": "object"}, "strict": False}}
    groq.replies = [limited, limited]
    with pytest.raises(ProviderRateLimited):
        adapter.complete(call())
    groq.replies = [(429, {}, {"retry-after": "120"})]
    with pytest.raises(ProviderRateLimited):
        adapter.complete(call())
    groq.replies = [(500, {}, {})]
    with pytest.raises(ProviderUnavailable):
        adapter.complete(call())
    # Groq's free tier refuses one request whose tokens exceed its per-minute limit; waiting cannot help.
    groq.replies = [(413, {"error": {"message": "Request too large"}}, {})]
    with pytest.raises(ProviderInputTooLarge):
        adapter.complete(call())


def test_groq_is_disabled_without_its_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert GroqGateway.from_environment() is None
    monkeypatch.setenv("GROQ_API_KEY", "gsk-synthetic")
    adapter = GroqGateway.from_environment()
    assert (adapter.provider, adapter.model, adapter.base_url) == ("groq", "openai/gpt-oss-120b",
                                                                   "https://api.groq.com/openai/v1")
    assert os.environ["GROQ_API_KEY"] == "gsk-synthetic"


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("VISION_LIVE_GROQ") != "1",
                    reason="Set VISION_LIVE_GROQ=1 and GROQ_API_KEY to send synthetic excerpts to Groq")
def test_live_groq_consolidation_on_the_synthetic_fixture(story):
    adapter = GroqGateway.from_environment()
    report = {}
    for i, (cutoff, text) in enumerate([(3, "Arthur at home after the war"), (2, "Arthur during the war"),
                                        (1, "Arthur at ten")]):
        if i:
            time.sleep(61)  # the free tier allows about one consolidation per minute (8,000 tokens)
        plan, expanded, _ = gathered(story, cutoff, text)
        derivation_id = consolidate(story.engine, plan, expanded, adapter)
        story.db.expire_all()
        derivation = story.db.get(Derivation, derivation_id)
        run = story.db.scalar(query(ModelRun).where(ModelRun.derivation_id == derivation_id))
        facts = story.db.scalars(query(VisualFact).where(VisualFact.derivation_id == derivation_id)).all()
        state = None
        if derivation.status == "succeeded":
            from app.services.reconstruction.context import appearance
            found, labels = appearance(story.db, plan, derivation_id)
            state = {"outcome": found.outcome, "event": labels.get(found.event), "unknown": found.unknown,
                     "traits": {k: [t.status, t.values] for k, t in found.traits.items()},
                     "choices": [labels.get(c) for c in found.choices]}
        report[text] = {"status": derivation.status, "error": derivation.error_code, "rejections": derivation.rejections,
                        "state": state,
                        "tokens": [run.input_tokens, run.output_tokens], "ms": run.duration_ms,
                        "facts": sorted(f"{f.attribute}={f.value} ({f.kind}, {f.support}, {f.modality}, "
                                        f"{f.polarity}, canonical={f.canonical})" for f in facts)}
    print(json.dumps(report, indent=1, ensure_ascii=False))
    assert all(r["status"] in {"succeeded", "failed"} for r in report.values())


@pytest.mark.integration
def test_registry_refs_publish_to_real_entities_without_widening_identity(story):
    plan, expanded, _ = gathered(story, 3, "Mira at dinner after the war")
    received = []
    def rule(sources):
        request = json.loads(next(s["text"] for s in sources if s["ref"] == "request"))
        received.append(request)
        mira = next(e["ref"] for e in request["entities"] if "mira" in e["aliases"])
        quote = "Mira sat opposite, holding her brass compass."
        ref = next(s["ref"] for s in sources if quote in s["text"])
        return {"events": [{"key": "dinner", "label": "dinner", "modality": "fact", "participants": [mira],
                            "evidence": [{"ref": ref, "quote": quote}]}],
                "facts": [{"subject": mira, "attribute": "held_object", "value": "brass compass", "kind": "scene",
                           "support": "explicit", "modality": "fact", "events": ["dinner"],
                           "evidence": [{"ref": ref, "quote": quote}]}], "requested_event": "dinner"}
    derivation = consolidate(story.engine, plan, expanded, RuleAdapter(rule))
    story.db.expire_all()
    facts = story.db.scalars(query(VisualFact).where(VisualFact.derivation_id == derivation)).all()
    assert len(facts) == 1 and facts[0].subject_id in plan.subject.entity_ids
    assert received and "entity:" in json.dumps(received)


@pytest.mark.integration
def test_changed_limits_do_not_reuse_a_consolidation(story):
    from app.services.retrieval.consolidation import LIMITS
    plan, expanded, _ = gathered(story, 2, "Arthur during the war")
    adapter = RuleAdapter(consolidation_rule)
    first = consolidate(story.engine, plan, expanded, adapter)
    changed = consolidate(story.engine, plan, expanded, adapter, LIMITS.model_copy(update={"max_output_tokens": 8192}))
    assert changed != first
    rows = story.db.scalars(query(ModelRun).where(ModelRun.derivation_id.in_([first, changed]))).all()
    assert {r.config["max_output_tokens"] for r in rows} == {4096, 8192}
