"""Expected inclusion/exclusion matrices for every annotated reconstruction case in the synthetic corpus."""

import json
from pathlib import Path

import pytest
from app.services.narrative.chronology import Chronology, Statement
from app.services.reconstruction.state import Fact, attribute_key, part, reconstruct

DATA = json.loads((Path(__file__).parent / "fixtures/narrative/expected.json").read_text(encoding="utf-8"))
CHAPTER = {p["id"]: p["chapter"] for p in DATA["passages"]}
SPAN_CHAPTER = {s["id"]: CHAPTER[s["passage_id"]] for s in DATA["spans"]}
KIND = {e["id"]: e["kind"] for e in DATA["entities"]}
# Annotated support -> (support, modality, polarity) as consolidation would store it.
SUPPORT = {"explicit": ("explicit", "fact", "affirmed"), "disputed": ("explicit", "fact", "affirmed"),
           "rumor": ("explicit", "rumor", "affirmed"), "metaphor": ("explicit", "metaphor", "affirmed"),
           "dream": ("explicit", "dream", "affirmed"), "negated": ("explicit", "fact", "negated")}
UNKNOWN = {"adult_hair": "hair"}


def visible(evidence, cutoff):
    return all(SPAN_CHAPTER[s] <= cutoff for s in evidence)


def facts_at(cutoff):
    # Annotated inferences are expected outputs, not inputs.
    return [Fact(f["id"], f["subject"], f["attribute"], f["value"], f["kind"], *SUPPORT[f["support"]],
                 frozenset(f["events"])) for f in DATA["facts"] if f["support"] in SUPPORT
            and visible(f["evidence"], cutoff)]


def chronology_at(cutoff, extra=()):
    statements = [Statement(r["from"], r["relation"], r["to"]) for r in DATA["temporal_relations"]
                  if visible(r["evidence"], cutoff)]
    return Chronology({e["id"]: "fact" for e in DATA["events"]}, [*statements, *extra])


def included(state, status):
    return {f for t in state.traits.values() if t.status == status for f in t.facts}


CASES = [c for c in DATA["cases"] if c["subject"]]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_annotated_case_matrix(case):
    cutoff = case["through_chapter"]
    state = reconstruct(facts_at(cutoff), {case["subject"]}, KIND[case["subject"]], case["event"], chronology_at(cutoff))
    everything = {f for t in state.traits.values() for f in t.facts}
    assert included(state, "canonical") == set(case["canonical"])
    assert included(state, "disputed") == set(case["disputed"])
    assert not set(case["excluded"]) & everything
    assert {UNKNOWN.get(u, u) for u in case["unknown"]} - {"identity"} <= set(state.unknown)
    if case["inferred"] == ["road-scar-inference"] or case["id"] == "unknown-journey-attire":
        # The annotation names the inference; reconstruction derives it from the war scar alone.
        scar = state.traits["left_cheek"]
        assert (scar.status, scar.facts, scar.values) == ("inferred", ["war-scar"], ["scar"])
        assert "no persistence" in scar.reason
    else:
        assert included(state, "inferred") == set()
    if case["id"] == "unknown-journey-attire":
        # The journey state itself resolves (an inferred scar); attire is the unknown the case asks about.
        assert "attire" in state.unknown and "attire" not in state.traits
    else:
        assert state.outcome == case["outcome"]


def test_reasons_for_exclusion_are_specific():
    state = reconstruct(facts_at(4), {"arthur"}, "character", "dinner", chronology_at(4))
    assert state.excluded["golden-eyes"] == "rumor" and state.excluded["wings"] == "dream"
    assert state.excluded["iron-body"] == "metaphor" and state.excluded["home-no-armor"] == "negated"
    assert state.excluded["war-armor"] in {"removed", "scene-specific"}
    assert state.excluded["child-hair"] == "tied to another moment"
    assert state.excluded["war-scar"] == "superseded at this moment"
    assert state.traits["eyes"].values == ["blue", "green"] and state.traits["eyes"].status == "disputed"
    child = reconstruct(facts_at(2), {"arthur"}, "character", "child", chronology_at(2))
    assert child.excluded["war-scar"] == "later in story time"


def test_direct_inferences_keep_a_reason_and_unexplained_inferences_are_excluded():
    facts = [Fact("roof", "house", "roof", "slate", "identity", "inferred", "fact", "affirmed",
                  frozenset({"dinner"}), "The roof material is inferred from the earlier description."),
             Fact("wall", "house", "wall", "stone", "identity", "inferred", "fact", "affirmed",
                  frozenset({"dinner"}))]
    state = reconstruct(facts, {"house"}, "place", "dinner", chronology_at(3))
    assert state.traits["roof"].status == "inferred" and state.traits["roof"].reason == facts[0].assumption
    assert "wall" not in state.traits and state.excluded["wall"] == "missing_assumption"


def test_multiple_direct_inference_reasons_stay_bounded_without_becoming_canonical():
    facts = [Fact(str(i), "house", "roof", value, "identity", "inferred", "fact", "affirmed",
                  frozenset({"dinner"}), reason) for i, (value, reason) in enumerate([
                      ("slate", "A" * 256), ("stone", "B" * 256)])]
    state = reconstruct(facts, {"house"}, "place", "dinner", chronology_at(3))
    trait = state.traits["roof"]
    assert trait.status == "inferred" and set(trait.values) == {"slate", "stone"}
    assert trait.reason and len(trait.reason) <= 256


def test_an_unspecified_moment_offers_choices_instead_of_blending():
    state = reconstruct(facts_at(3), {"arthur"}, "character", None, chronology_at(3))
    assert (state.outcome, state.choices) == ("needs_context", ["child", "war", "dinner"])
    house = reconstruct(facts_at(1), {"house"}, "place", None, chronology_at(1))
    assert (house.outcome, house.event, house.traits["roof"].values) == ("resolved", "child", ["intact slate"])


def test_unordered_events_and_untimed_traits_stay_uncertain():
    facts = [Fact("north-coat", "mira", "attire", "fur coat", "scene", "explicit", "fact", "affirmed",
                  frozenset({"north-voyage"})),
             Fact("north-tan", "mira", "skin", "sunburnt", "acquired", "explicit", "fact", "affirmed",
                  frozenset({"north-voyage"})),
             Fact("eyes", "mira", "eyes", "grey", "identity", "explicit", "fact", "affirmed", frozenset())]
    state = reconstruct(facts, {"mira"}, "character", "south-voyage", chronology_at(5))
    assert state.excluded == {"north-coat": "order unknown", "north-tan": "order unknown"}
    assert (state.traits["eyes"].status, state.traits["eyes"].reason) == ("inferred", "stated without a story moment")
    assert set(state.unknown) == {"hair", "eyes", "attire"}


def test_sub_attributes_are_separate_traits_but_share_supersession():
    def fact(id, attribute, value, kind, events):
        return Fact(id, "arthur", attribute, value, kind, "explicit", "fact", "affirmed", frozenset(events))
    facts = [fact("blue", "coat_color", "blue", "scene", {"child"}), fact("wool", "coat_material", "wool", "scene", {"child"}),
             fact("unmarked", "left_cheek_marked", "unmarked", "acquired", {"child"}),
             fact("scar", "left_cheek_scar", "scar", "acquired", {"war"})]
    child = reconstruct(facts, {"arthur"}, "character", "child", chronology_at(2))
    assert {k: t.status for k, t in child.traits.items()} == {
        "coat_color": "canonical", "coat_material": "canonical", "left_cheek_marked": "canonical"}
    assert "attire" not in child.unknown
    war = reconstruct(facts, {"arthur"}, "character", "war", chronology_at(2))
    assert set(war.traits) == {"left_cheek_scar"} and war.excluded["unmarked"] == "superseded at this moment"


def test_model_attribute_names_group_under_core_traits():
    assert [attribute_key(a) for a in ("hair_color", "eye_color", "eyes", "clothing", "armor_material",
                                       "attire_exclusion", "left_cheek")] == [
        "hair", "eyes", "eyes", "attire", "attire", "attire", "left_cheek"]
    assert attribute_key("blade_material") == "material"
    assert [attribute_key(a) for a in ("wearing", "worn_items", "wears")] == ["attire"] * 3
    assert [part(a) for a in ("left_cheek_scar", "left_cheek", "coat_color", "eye_color", "attire_exclusion")] == [
        "left_cheek", "left_cheek", "coat", "eyes", "attire"]


QUOTE = {s["id"]: s["quote"] for s in DATA["spans"]}
NAMES = {"arthur": "Arthur", "elodie": "Élodie", "mira": "Mira", "brann": "Brann", "wren": "Wren",
         "house": "house by the ash tree", "compass": "brass compass", "sword": "silver sword"}
# Most specific phrase first: "travelling home after the war" is the journey, not the dinner.
MOMENTS = {"age 10": "child", "during the war": "war", "travelling home": "journey", "spring": "spring",
           "at dinner": "dinner", "after the war": "dinner"}


def annotated_consolidation(sources):
    """An 'ideal model': the annotated events, relations and facts whose quotes are in the excerpts."""
    text = {s["ref"]: s["text"] for s in sources if s["ref"] != "request"}
    request = json.loads(next(s["text"] for s in sources if s["ref"] == "request"))

    def evidence(spans, partial=False):
        found = [{"ref": next((r for r, t in text.items() if QUOTE[s] in t), None), "quote": QUOTE[s]} for s in spans]
        present = [e for e in found if e["ref"]]
        return present if present and (partial or len(present) == len(found)) else None

    # An event needs only one quote in the excerpts; facts and relations need all of theirs.
    events = [{"key": e["id"], "label": e["id"], "modality": "fact", "participants": [NAMES[p] for p in e["participants"]],
               "evidence": evidence(e["evidence"], True)} for e in DATA["events"] if evidence(e["evidence"], True)]
    keys = {e["key"] for e in events}
    relations = [{"source": r["from"], "relation": r["relation"], "target": r["to"], **evidence(r["evidence"][:1])[0]}
                 for r in DATA["temporal_relations"] if {r["from"], r["to"]} <= keys and evidence(r["evidence"][:1])]
    facts = []
    for f in DATA["facts"]:
        if f["support"] not in SUPPORT or not evidence(f["evidence"]):
            continue
        support, modality, polarity = SUPPORT[f["support"]]
        facts.append({"subject": NAMES[f["subject"]], "attribute": f["attribute"].replace("_exclusion", ""),
                      "value": f["value"], "kind": f["kind"], "support": support, "modality": modality,
                      "polarity": polarity, "events": [e for e in f["events"] if e in keys],
                      "evidence": evidence(f["evidence"])})
    moment = next((event for phrase, event in MOMENTS.items()
                   if phrase in f"{request['request']} {request['moment']} {request['scene']}" and event in keys), None)
    return {"events": events, "relations": relations, "facts": facts, "requested_event": moment}


def stored_values(story, state):
    from app.models.visual_facts import VisualFact
    return {status: sorted(story.db.get(VisualFact, f).value for t in state.traits.values() if t.status == status
                           for f in t.facts) for status in ("canonical", "inferred", "disputed")}


@pytest.mark.integration
def test_states_from_a_stored_consolidation(story):
    from app.models.model_runs import Derivation
    from app.providers.deterministic import RuleAdapter
    from app.services.reconstruction.context import appearance
    from app.services.retrieval.consolidation import consolidate
    from tests.test_evidence_consolidation import gathered

    def state(cutoff, query):
        plan, expanded, _ = gathered(story, cutoff, query)
        derivation_id = consolidate(story.engine, plan, expanded, RuleAdapter(annotated_consolidation))
        story.db.expire_all()
        derivation = story.db.get(Derivation, derivation_id)
        assert derivation.status == "succeeded"
        return appearance(story.db, plan, derivation_id)[0]

    child = state(1, "Arthur at ten")
    assert stored_values(story, child)["canonical"] == ["blue wool coat", "chestnut", "unmarked"]
    war = state(2, "Arthur during the war")
    assert stored_values(story, war)["canonical"] == ["scar", "steel armor"]
    assert "eyes" in war.unknown
    home = state(3, "Arthur at home after the war")
    assert stored_values(story, home)["canonical"] == ["plain linen shirt", "scar still visible"]
    assert {"hair", "eyes"} <= set(home.unknown)
    disputed = state(4, "Arthur at home after the war")
    assert stored_values(story, disputed)["disputed"] == ["blue", "green"]
    unspecified = state(3, "Arthur")
    assert unspecified.outcome == "needs_context" and len(unspecified.choices) == 3
    unanchored = state(2, "Arthur in spring")
    assert (unanchored.outcome, unanchored.unknown) == ("insufficient_evidence", ["moment"])


def test_unexplained_negated_inference_cannot_remove_an_earlier_fact():
    facts = [Fact("old", "arthur", "left_cheek", "scar", "acquired", "explicit", "fact", "affirmed", frozenset({"war"})),
             Fact("bad", "arthur", "left_cheek", "scar", "acquired", "inferred", "fact", "negated",
                  frozenset({"dinner"}), "   ")]
    state = reconstruct(facts, {"arthur"}, "character", "dinner", chronology_at(3))
    assert state.traits["left_cheek"].values == ["scar"]
    assert state.excluded["bad"] == "missing_assumption"


def test_carried_inference_keeps_its_assumption_without_calling_it_stated():
    assumption = "Material inferred from a similar roof."
    fact = Fact("roof", "house", "roof_material", "slate", "identity", "inferred", "fact", "affirmed",
                frozenset(), assumption)
    state = reconstruct([fact], {"house"}, "place", "dinner", chronology_at(3))
    assert assumption in state.traits["roof_material"].reason
    assert "stated without" not in state.traits["roof_material"].reason
