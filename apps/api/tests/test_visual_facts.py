import json
import os

import pytest
from app.models.entities import Entity
from app.models.events import Event
from app.models.model_runs import Derivation, ModelRun
from app.models.passages import Passage
from app.models.visual_facts import FactConflict, FactEvent, FactEvidence, VisualFact
from app.providers.contracts import Limits, ProviderRequest
from app.providers.deterministic import RuleAdapter, ScriptedAdapter
from app.providers.execution import execute
from app.providers.openai_compatible import ChatGateway
from app.providers.visual_facts import KNOWN_REF, FactExtraction
from app.services.narrative.entities import derive_entities
from app.services.narrative.events import derive_events
from app.services.narrative.visual_facts import assertion_problem, derive_visual_facts
from app.services.reconstruction.conflicts import Claim, conflicts, summarize
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.test_chronology import event_rule
from tests.test_entity_extraction import fixture_adapter, generation  # noqa: F401  (shared fixture)

INJURY = "Ten years later, during the war, a blade cut Arthur's left cheek and left a scar."
NEGATION = '"Are you wearing armor?" Élodie asked Arthur. "No, I removed it before dinner," he replied.'
OWNER = "Brann, not Arthur, held the silver sword."
# subject, attribute, value, kind, support, modality, polarity, events, quote, extra
FACTS = [
    ("Arthur", "hair", "chestnut", "identity", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "At ten, Arthur had chestnut hair and an unmarked left cheek.", {}),
    ("Arthur", "left_cheek", "unmarked", "interval", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "At ten, Arthur had chestnut hair and an unmarked left cheek.", {}),
    ("Arthur", "attire", "blue wool coat", "scene", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "He wore a blue wool coat beside the house by the ash tree.", {}),
    ("Arthur", "left_cheek", "scar", "acquired", "explicit", "fact", "affirmed", ["the war"], INJURY, {}),
    ("Arthur", "attire", "steel armor", "scene", "explicit", "fact", "affirmed", ["the war"], "Arthur wore steel armor.", {}),
    ("Arthur", "attire", "plain linen shirt", "scene", "explicit", "fact", "affirmed", ["dinner"],
     "Before dinner, Arthur removed his steel armor and put on a plain linen shirt.", {}),
    ("Arthur", "left_cheek", "scar still visible", "acquired", "explicit", "fact", "affirmed", ["dinner"],
     "At dinner his left-cheek scar was still visible.", {}),
    ("Arthur", "attire", "steel armor", "scene", "explicit", "fact", "negated", ["dinner"], NEGATION, {}),
    ("Arthur", "eyes", "golden", "identity", "explicit", "rumor", "affirmed", [],
     "People claim Arthur has golden eyes, but I have never seen them.", {"perspective": "a messenger"}),
    ("Arthur", "body", "wolf made of iron", "identity", "explicit", "metaphor", "affirmed", [],
     "A poet called Arthur a wolf made of iron.", {"perspective": "a poet"}),
    ("Arthur", "body", "wings", "scene", "explicit", "dream", "affirmed", ["Arthur dreams of wings"],
     "That night Arthur dreamed that he had wings.", {}),
    ("Arthur", "eyes", "green", "scene", "explicit", "fact", "affirmed", ["dinner"], "One said his eyes were green;",
     {"perspective": "first signed record"}),
    ("Arthur", "eyes", "blue", "scene", "explicit", "fact", "affirmed", ["dinner"], "the other said his eyes were blue.",
     {"perspective": "second signed record"}),
    ("house by the ash tree", "roof", "intact slate", "interval", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "The house had an intact slate roof.", {}),
    ("house by the ash tree", "roof", "destroyed", "acquired", "explicit", "fact", "affirmed", ["fire destroys the roof"],
     "During the same battle, fire destroyed the house's slate roof.", {}),
    ("house by the ash tree", "roof", "missing", "interval", "explicit", "fact", "affirmed", ["dinner"],
     "The house's roof was still missing when they returned.", {}),
    ("house by the ash tree", "roof", "restored slate", "acquired", "explicit", "fact", "affirmed", ["roof restored"],
     "By the following spring, builders had restored the slate roof.", {}),
    ("brass compass", "material", "brass", "identity", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "Captain Mira carried a brass compass.", {}),
    ("silver sword", "material", "silver", "identity", "explicit", "fact", "affirmed", [],
     "Captain Brann carried a silver sword.", {}),
    ("Mira", "held_object", "compass", "scene", "explicit", "fact", "affirmed", ["Arthur at ten"],
     "Captain Mira carried a brass compass.", {}),
    ("Brann", "held_object", "silver sword", "scene", "explicit", "fact", "affirmed", ["the war"], OWNER, {}),
    ("Arthur", "left_cheek", "unmarked", "interval", "explicit", "memory", "affirmed", ["Arthur at ten"],
     "Élodie remembered Arthur at ten, before the war: his left cheek was unmarked as he stood beside the ash tree.",
     {"perspective": "Élodie"}),
    ("Mira", "held_object", "brass compass", "scene", "explicit", "fact", "affirmed", ["dinner"],
     "Élodie sat beside him; Mira sat opposite, holding her brass compass.", {}),
    ("Arthur", "left_cheek", "scar possibly persists; no ending established", "acquired", "inferred", "fact",
     "affirmed", ["journey home"], "After the war, Arthur travelled home.",
     {"assumption": "The war scar is not described on the road and no healing is stated."}),
    # The gates reject the rest: no passage names the house beside the candlelight, ...
    ("house by the ash tree", "lighting", "warm candlelight", "scene", "explicit", "fact", "affirmed", ["dinner"],
     "Warm candlelight lit the room.", {}),
    # ... the sword is Brann's, armor is only asked about, a quote is invented, a scene has no event, ...
    ("Arthur", "held_object", "silver sword", "scene", "explicit", "fact", "affirmed", ["the war"], OWNER, {}),
    ("Arthur", "attire", "steel armor", "scene", "explicit", "fact", "affirmed", ["dinner"], NEGATION, {}),
    ("Arthur", "hair", "golden", "identity", "explicit", "fact", "affirmed", [], "Arthur's golden hair shone.", {}),
    ("Arthur", "attire", "blue wool coat", "scene", "explicit", "fact", "affirmed", [],
     "He wore a blue wool coat beside the house by the ash tree.", {}),
    # ... and an unknown subject.
    ("Ghost", "hair", "white", "identity", "explicit", "fact", "affirmed", [], "Arthur wore steel armor.", {}),
]


def fact_rule(sources):
    known = {e["label"]: e["key"] for s in sources if s["ref"] == KNOWN_REF for e in json.loads(s["text"])}
    text = [s for s in sources if s["ref"] != KNOWN_REF]
    facts = []
    for subject, attribute, value, kind, support, modality, polarity, events, quote, extra in FACTS:
        ref = next((s["ref"] for s in text if quote in s["text"]), None)
        if ref is None and quote.startswith("Arthur's golden"):
            ref = next((s["ref"] for s in text if "Arthur wore steel armor." in s["text"]), None)
        if ref is None:
            continue
        facts.append({"subject": subject, "attribute": attribute, "value": value, "kind": kind, "support": support,
                      "modality": modality, "polarity": polarity, "events": [known[e] for e in events if e in known],
                      "evidence": [{"ref": ref, "quote": quote}], **extra})
    return {"facts": facts}


def test_assertion_gate_rejects_questions_and_negations_but_not_negated_names():
    assert assertion_problem("steel armor", [NEGATION]) == "negated_or_question"
    assert assertion_problem("steel armor", ["Arthur never wore steel armor."]) == "negated_or_question"
    assert assertion_problem("silver sword", [OWNER]) is None
    rumor = "People claim Arthur has golden eyes, but I have never seen them."
    assert assertion_problem("golden", [rumor]) is None  # a rumor may say it; canon may not
    assert assertion_problem("golden", [rumor], canonical_modality=True) == "speculative"
    assert assertion_problem("purple", ["Arthur wore steel armor."]) == "value_ungrounded"
    removed = "Before dinner, Arthur removed his steel armor and put on a plain linen shirt."
    assert assertion_problem("steel armor", [removed]) == "negated_or_question"
    assert assertion_problem("plain linen shirt", [removed], canonical_modality=True) is None


def test_conflicts_and_summary_keep_disputes_and_unknowns_visible():
    dinner, child = "dinner", "child"
    claims = [Claim(1, "arthur", "eyes", "green", "scene", frozenset({dinner}), True),
              Claim(2, "arthur", "eyes", "blue", "scene", frozenset({dinner}), True),
              Claim(3, "arthur", "eyes", "golden", "identity", frozenset(), False),
              Claim(4, "arthur", "hair", "chestnut", "identity", frozenset({child}), True),
              Claim(5, "arthur", "attire", "plain linen shirt", "scene", frozenset({dinner}), True),
              Claim(6, "house", "roof", "intact slate", "interval", frozenset({child}), True),
              Claim(7, "house", "roof", "Intact slate ", "interval", frozenset({child}), True),
              Claim(8, "sword", "material", "silver", "identity", frozenset(), True),
              Claim(9, "sword", "material", "steel", "identity", frozenset(), True)]
    assert conflicts(claims) == {frozenset({1, 2}), frozenset({8, 9})}
    assert summarize(claims, "arthur", dinner, ["eyes", "hair", "attire"]) == {
        "eyes": ("disputed", ["blue", "green"]), "hair": ("unknown", None), "attire": ("known", "plain linen shirt")}


def test_creative_support_is_not_a_valid_extraction_outcome():
    output = json.dumps({"facts": [{"subject": "Arthur", "attribute": "cape", "value": "red", "kind": "scene",
                                    "support": "creative", "modality": "fact", "events": ["e:0"],
                                    "evidence": [{"ref": "p0", "quote": "x"}]}]})
    request = ProviderRequest(role="extraction", purpose="test.facts", prompt_version="t", instructions="x")
    assert execute(ScriptedAdapter(output), request, FactExtraction).record.outcome == "invalid_output"


@pytest.mark.integration
def test_fixture_facts_keep_owner_scope_modality_and_conflicts(database, generation):  # noqa: F811
    entities = derive_entities(database, generation, fixture_adapter())
    events = derive_events(database, generation, entities, RuleAdapter(event_rule))
    derivation_id = derive_visual_facts(database, generation, events, RuleAdapter(fact_rule))
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        assert (derivation.status, derivation.input_derivation_id) == ("succeeded", events)
        assert derivation.rejections == {"unattributed": 1, "wrong_owner": 1, "negated_or_question": 1,
                                         "ungrounded": 1, "unscoped_scene": 1, "unknown_subject": 1}
        rows = db.execute(select(VisualFact, Entity.label).join(Entity, Entity.id == VisualFact.subject_id)
                          .where(VisualFact.derivation_id == derivation_id)).all()
        facts = {(label, f.attribute, f.value, f.modality, f.polarity): f for f, label in rows}
        assert len(facts) == 24
        assert ("Arthur", "held_object", "silver sword", "fact", "affirmed") not in facts
        assert ("Brann", "held_object", "silver sword", "fact", "affirmed") in facts
        assert not facts[("Arthur", "attire", "steel armor", "fact", "negated")].canonical
        assert not facts[("Arthur", "eyes", "golden", "rumor", "affirmed")].canonical
        assert not facts[("Arthur", "body", "wings", "dream", "affirmed")].canonical
        inferred = facts[("Arthur", "left_cheek", "scar possibly persists; no ending established", "fact", "affirmed")]
        assert inferred.support == "inferred" and not inferred.canonical and inferred.assumption
        assert facts[("Arthur", "eyes", "green", "fact", "affirmed")].perspective == "first signed record"

        event_of = {e.id: e.label for e in db.scalars(select(Event).where(Event.derivation_id == events))}
        linked = {}
        for link in db.scalars(select(FactEvent).join(VisualFact).where(VisualFact.derivation_id == derivation_id)):
            linked.setdefault(link.fact_id, set()).add(event_of[link.event_id])
        for key, fact in facts.items():
            if fact.kind == "scene":
                assert linked.get(fact.id), key  # scene facts are scoped to their event, never persistent
        assert linked[facts[("Arthur", "attire", "steel armor", "fact", "affirmed")].id] == {"the war"}
        for evidence in db.scalars(select(FactEvidence).join(VisualFact).where(VisualFact.derivation_id == derivation_id)):
            assert db.get(Passage, evidence.passage_id).text[evidence.start:evidence.end]

        disputes = db.scalars(select(FactConflict).where(FactConflict.derivation_id == derivation_id)).all()
        assert [(d.status, {db.get(VisualFact, d.fact_a_id).value, db.get(VisualFact, d.fact_b_id).value})
                for d in disputes] == [("unresolved", {"green", "blue"})]
        claims = [Claim(f.id, label, f.attribute, f.value, f.kind, frozenset(linked.get(f.id, ())), f.canonical)
                  for f, label in rows]
        assert summarize(claims, "Arthur", "dinner", ["eyes", "hair", "attire", "left_cheek"]) == {
            "eyes": ("disputed", ["blue", "green"]), "hair": ("unknown", None),
            "attire": ("known", "plain linen shirt"), "left_cheek": ("known", "scar still visible")}
        house = summarize(claims, "house by the ash tree", "dinner", ["roof", "lighting"])
        assert house == {"roof": ("known", "missing"), "lighting": ("unknown", None)}


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("VISION_LIVE_PROVIDER") != "1" or not os.environ.get("VISION_LLM_API_KEY"),
                    reason="Set VISION_LIVE_PROVIDER=1 and VISION_LLM_API_KEY to send the synthetic corpus to the gateway")
def test_live_gateway_events_and_facts_on_the_synthetic_fixture(database, generation):  # noqa: F811
    adapter, limits = ChatGateway.from_environment(), Limits(timeout_seconds=120, max_output_tokens=8_192)
    stages = []
    for derive in (lambda: derive_entities(database, generation, adapter, limits),
                   lambda: derive_events(database, generation, stages[-1], adapter, limits),
                   lambda: derive_visual_facts(database, generation, stages[-1], adapter, limits)):
        stages.append(derive())
        with Session(database) as db:
            if db.get(Derivation, stages[-1]).status != "succeeded":
                break  # a later stage only runs on a succeeded input
    with Session(database) as db:
        derivations = [db.get(Derivation, d) for d in stages]
        runs = db.execute(select(ModelRun.derivation_id, ModelRun.outcome, ModelRun.model_version)
                          .where(ModelRun.derivation_id.in_(stages)).order_by(ModelRun.started_at)).all()
        rows = db.execute(select(VisualFact, Entity.label).join(Entity, Entity.id == VisualFact.subject_id)
                          .where(VisualFact.derivation_id == stages[-1])).all()
        disputes = db.scalars(select(FactConflict).where(FactConflict.derivation_id == stages[-1])).all()
        for evidence in db.scalars(select(FactEvidence).join(VisualFact).where(VisualFact.derivation_id == stages[-1])):
            assert db.get(Passage, evidence.passage_id).text[evidence.start:evidence.end]
        names = {d.id: d.stage for d in derivations}
        report = {
            "stages": [(d.stage, d.status, d.error_code, d.rejections) for d in derivations],
            "runs": [(names[d], outcome, model) for d, outcome, model in runs],
            "facts": sorted(f"{label} | {f.attribute} = {f.value} | {f.kind}/{f.support}/{f.modality}/{f.polarity}"
                            f"{' | canonical' if f.canonical else ''}" for f, label in rows),
            "conflicts": sorted(sorted([db.get(VisualFact, d.fact_a_id).value, db.get(VisualFact, d.fact_b_id).value])
                                for d in disputes),
        }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    assert derivations[0].status == "succeeded"
