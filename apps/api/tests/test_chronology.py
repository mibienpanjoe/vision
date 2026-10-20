import json

import pytest
from app.models.entities import Entity
from app.models.events import (
    Event,
    EventEvidence,
    EventParticipant,
    EventRelation,
    TemporalAnchor,
)
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.providers.deterministic import RuleAdapter
from app.providers.events import KNOWN_REF
from app.services.narrative.chronology import Chronology, Statement
from app.services.narrative.entities import derive_entities
from app.services.narrative.events import chronology, derive_events
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.test_entity_extraction import fixture_adapter, generation  # noqa: F401  (shared fixture)

FACTS = {name: "fact" for name in ("child", "war", "journey", "removal", "dinner", "spring", "north", "south")}


def chain(*names):
    return [Statement(a, "before", b) for a, b in zip(names, names[1:])]


def test_fixture_partial_order_is_transitive_and_keeps_unknowns():
    story = Chronology(FACTS, chain("child", "war", "journey", "removal", "dinner", "spring")
                       + [Statement("north", "unknown", "south")])
    assert story.order("child", "spring") == "before" and story.order("spring", "child") == "after"
    assert story.order("north", "south") == "unknown" and story.order("north", "war") == "unknown"
    assert story.inconsistencies() == set()


def test_during_inherits_order_and_after_is_normalised():
    story = Chronology({**FACTS, "battle": "fact"},
                       [Statement("battle", "during", "war"), Statement("journey", "after", "war")])
    assert story.order("battle", "journey") == "before"
    assert story.order("battle", "war") == "overlaps"


def test_cycles_and_overlap_conflicts_never_support_a_definite_order():
    events = {name: "fact" for name in "abcxy"}
    story = Chronology(events, chain("x", "a", "b", "c", "a") + chain("c", "y"))
    assert story.order("a", "b") == story.order("x", "a") == "inconsistent"
    assert story.order("x", "y") == "unknown"  # only reachable through the contradiction
    clash = Chronology({"p": "fact", "q": "fact"}, [Statement("p", "before", "q"), Statement("p", "overlaps", "q")])
    assert clash.order("p", "q") == "inconsistent" and clash.inconsistencies() == {frozenset("pq")}


def test_dreams_rumors_and_metaphors_are_not_chronology_updates():
    events = {**FACTS, "wings": "dream", "golden": "rumor", "iron": "metaphor", "memory": "memory"}
    story = Chronology(events, chain("child", "war", "journey") + [
        Statement("wings", "after", "journey"), Statement("golden", "before", "child"),
        Statement("iron", "during", "war"), Statement("memory", "during", "child")])
    assert {story.order(e, "journey") for e in ("wings", "golden", "iron")} == {"unknown"}
    assert story.order("memory", "war") == "before"


EVENTS = [  # key, label, modality, participants, evidence quote
    ("child", "Arthur at ten", "fact", ["Arthur", "Élodie", "Mira", "Brann", "Wren", "Nobody"],
     "At ten, Arthur had chestnut hair and an unmarked left cheek."),
    ("war", "the war", "fact", ["Arthur"], "during the war, a blade cut Arthur's left cheek and left a scar."),
    ("wings", "Arthur dreams of wings", "dream", ["Arthur"], "That night Arthur dreamed that he had wings."),
    ("roof", "fire destroys the roof", "fact", [], "fire destroyed the house's slate roof."),
    ("journey", "journey home", "fact", ["Arthur"], "After the war, Arthur travelled home."),
    ("removal", "armor removed", "fact", ["Arthur"], "Before dinner, Arthur removed his steel armor"),
    ("dinner", "dinner", "fact", ["Arthur", "Élodie", "Mira"], "At dinner his left-cheek scar was still visible."),
    ("spring", "roof restored", "fact", [], "By the following spring, builders had restored the slate roof."),
    ("north", "Mira's northern voyage", "fact", ["Mira"], "The dates of Mira's northern voyage"),
    ("south", "Brann's southern voyage", "fact", ["Brann"], "Brann's southern voyage were lost."),
    ("memory", "Élodie remembers Arthur at ten", "memory", ["Élodie", "Arthur"], "Élodie remembered Arthur at ten"),
    ("ghost", "invented event", "fact", [], "Arthur crowned himself king."),
]
RELATIONS = [("child", "before", "war", "Ten years later, during the war"),
             ("wings", "during", "war", "That night Arthur dreamed"),
             ("roof", "during", "war", "During the same battle, fire destroyed the house's slate roof."),
             ("war", "before", "journey", "After the war, Arthur travelled home."),
             ("journey", "before", "removal", "After the war, Arthur travelled home."),
             ("removal", "before", "dinner", "Before dinner, Arthur removed his steel armor"),
             ("dinner", "before", "spring", "By the following spring"),
             ("north", "unknown", "south", "No account established which voyage happened first"),
             ("memory", "during", "child", "Élodie remembered Arthur at ten, before the war"),
             ("memory", "before", "k:99", "Élodie remembered Arthur at ten")]


def event_rule(sources):
    known = {e["label"]: e["key"] for s in sources if s["ref"] == KNOWN_REF for e in json.loads(s["text"])}
    text = [s for s in sources if s["ref"] != KNOWN_REF]
    found = lambda quote: next((s["ref"] for s in text if quote in s["text"]), None)  # noqa: E731
    label_of = {key: label for key, label, *_ in EVENTS}
    declared = {}
    for key, label, modality, participants, quote in EVENTS:
        ref = found(quote) if key != "ghost" else found("Arthur")
        if ref and label not in known:
            declared[key] = {"key": key, "label": label, "modality": modality, "participants": participants,
                             "evidence": [{"ref": ref, "quote": quote}]}
    if "ghost" in declared:  # hostile: cite the derived list as if it were source text
        declared["ghost"]["evidence"].append({"ref": KNOWN_REF, "quote": "k:0"})

    def key_of(key):
        return key if key in declared else known.get(label_of.get(key), key if key.startswith("k:") else None)

    relations = [{"source": key_of(s), "relation": r, "target": key_of(t), "ref": found(q), "quote": q}
                 for s, r, t, q in RELATIONS if found(q) and key_of(s) and key_of(t)]
    anchors = [{"event": "child", "kind": "age", "value": "ten", "ref": found("At ten"), "quote": "At ten"}] \
        if "child" in declared else []
    return {"events": list(declared.values()), "anchors": anchors, "relations": relations}


@pytest.mark.integration
def test_fixture_events_keep_modality_participants_and_two_time_axes(database, generation):  # noqa: F811
    entities = derive_entities(database, generation, fixture_adapter())
    adapter = RuleAdapter(event_rule)
    seen = []
    inner = adapter.complete
    adapter.complete = lambda call: seen.append(call) or inner(call)
    derivation_id = derive_events(database, generation, entities, adapter)
    assert KNOWN_REF not in seen[0].data and KNOWN_REF in seen[1].data
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        assert (derivation.status, derivation.input_derivation_id) == ("succeeded", entities)
        assert derivation.rejections == {"ungrounded": 2, "unmentioned_event": 1, "unknown_participant": 1,
                                         "unknown_event": 1}
        events = {e.label: e for e in db.scalars(select(Event).where(Event.derivation_id == derivation_id))}
        assert len(events) == 11 and events["Arthur dreams of wings"].modality == "dream"
        assert events["Élodie remembers Arthur at ten"].modality == "memory"
        participants = set(db.scalars(select(Entity.label).join(EventParticipant, EventParticipant.entity_id == Entity.id)
                                      .where(EventParticipant.event_id == events["Arthur at ten"].id)))
        assert participants == {"Arthur", "Élodie", "Mira", "Brann", "Wren"}
        anchor = db.scalar(select(TemporalAnchor).where(TemporalAnchor.event_id == events["Arthur at ten"].id))
        assert (anchor.kind, anchor.value, db.get(Passage, anchor.passage_id).text[anchor.start:anchor.end]) == (
            "age", "ten", "At ten")
        for evidence in db.scalars(select(EventEvidence).join(Event).where(Event.derivation_id == derivation_id)):
            assert db.get(Passage, evidence.passage_id).text[evidence.start:evidence.end]

        story, ids = chronology(db, derivation_id), {label: e.id for label, e in events.items()}
        assert story.order(ids["Arthur at ten"], ids["roof restored"]) == "before"
        assert story.order(ids["fire destroys the roof"], ids["journey home"]) == "before"
        assert story.order(ids["Mira's northern voyage"], ids["Brann's southern voyage"]) == "unknown"
        assert story.order(ids["Arthur dreams of wings"], ids["journey home"]) == "unknown"
        memory, war = ids["Élodie remembers Arthur at ten"], ids["the war"]
        assert story.order(memory, war) == "before"  # early in story time ...

        def revealed(event_id):
            return min(db.scalars(select(Passage.ordinal).join(EventEvidence, EventEvidence.passage_id == Passage.id)
                                  .where(EventEvidence.event_id == event_id)))
        assert revealed(memory) > revealed(war)  # ... but late in the source
        assert story.inconsistencies() == set()
        assert db.scalar(select(func.count()).select_from(EventRelation)
                         .where(EventRelation.derivation_id == derivation_id)) == 9


@pytest.mark.integration
def test_events_require_a_succeeded_entity_input_and_follow_its_version(database, generation):  # noqa: F811
    first = derive_entities(database, generation, fixture_adapter())
    second = derive_entities(database, generation, fixture_adapter("rule-v2"))
    adapter = RuleAdapter(event_rule)
    one, two = derive_events(database, generation, first, adapter), derive_events(database, generation, second, adapter)
    assert one != two and derive_events(database, generation, first, adapter) == one
    with Session(database) as db:
        db.get(Derivation, second).status = "failed"
        db.commit()
    with pytest.raises(ValueError):
        derive_events(database, generation, second, adapter)
    with pytest.raises(ValueError):
        derive_events(database, generation, one, adapter)
