"""Scene composition from the annotated corpus: admissible members, scoped props and evidence-only world context."""

import pytest
from app.services.reconstruction.scene import Entity, absentees, compose_scene
from app.services.reconstruction.state import Fact
from tests.test_appearance_states import DATA, chronology_at, facts_at

ENTITIES = {e["id"]: Entity(frozenset({e["id"]}), e["kind"], {"wren": "Wren", "house": "house by the ash tree",
                                                               "compass": "brass compass", "sword": "silver sword"}
                            .get(e["id"], e["name"])) for e in DATA["entities"]}
PARTICIPANTS = {e["id"]: set(e["participants"]) for e in DATA["events"]}
CARRIERS = {"brass compass": "Mira", "silver sword": "Brann"}
TEXT = {p["id"]: p["text"] for p in DATA["passages"]}


def scene_at(event, cutoff, subject="arthur", requested=(), extra=()):
    entities = [e for e in ENTITIES.values() if e.label != "unresolved masked visitor"]
    texts = [TEXT[p["id"]] for p in DATA["passages"] if p["chapter"] <= cutoff]
    return compose_scene([*facts_at(cutoff), *extra], chronology_at(cutoff), event, ENTITIES[subject], entities,
                         PARTICIPANTS[event], [ENTITIES[r] for r in requested], absentees(texts, entities), CARRIERS)


def labels_of(members):
    return {m.entity.label: m.role for m in members}


def test_family_dinner_has_only_admissible_members_with_their_own_states():
    scene = scene_at("dinner", 3, requested=["brann", "sword"])
    expected = DATA["scenes"][0]
    assert labels_of(scene.members) == {"Arthur": "subject", "Élodie": "participant", "Mira": "participant",
                                     "brass compass": "object"}
    assert {ENTITIES[p].label for p in expected["participants"]} | {"brass compass"} == set(labels_of(scene.members))
    assert scene.excluded == {"Brann": "absent from this scene", "silver sword": "absent from this scene"}
    states = {m.entity.label: m.state for m in scene.members}
    assert states["Arthur"].traits["attire"].values == ["plain linen shirt"]
    assert "held_object" not in states["Arthur"].traits  # Mira's compass stays Mira's
    assert states["Mira"].traits["held_object"].values == ["brass compass"]
    # The material was stated at the childhood event only; carrying it would need an explicit persistence claim.
    compass = states["brass compass"]
    assert "material" in compass.unknown and compass.excluded["compass-brass"] == "tied to another moment"


def test_world_context_comes_only_from_places_with_evidence_at_the_event():
    dinner = scene_at("dinner", 3)
    house = dinner.world[0].state
    assert labels_of(dinner.world) == {"house by the ash tree": "place"}
    assert (house.traits["lighting"].values, house.traits["roof"].values) == (["warm candlelight"], ["missing"])
    journey = scene_at("journey", 3)
    assert journey.world == [] and journey.unknown == ["setting"]
    invented = Fact("invented-fog", "house", "weather", "thick fog", "scene", "inferred", "fact", "affirmed",
                    frozenset({"dinner"}), "Fog is a model assumption, not an explicitly stated condition.")
    fog = scene_at("dinner", 3, extra=[invented]).world[0].state.traits["weather"]
    assert (fog.status, fog.values) == ("inferred", ["thick fog"])


def test_incompatible_moments_and_the_reading_boundary_hold_per_member():
    war = scene_at("war", 2)
    assert labels_of(war.members)["Arthur"] == "subject" and "Mira" in labels_of(war.members)
    arthur = next(m.state for m in war.members if m.entity.label == "Arthur")
    assert arthur.traits["attire"].values == ["steel armor"] and "held_object" not in arthur.traits
    child = scene_at("child", 1)
    child_arthur = next(m.state for m in child.members if m.entity.label == "Arthur")
    assert "war-scar" not in {f for t in child_arthur.traits.values() for f in t.facts}
    early = scene_at("dinner", 2)  # the dinner is not readable yet
    assert early.outcome == "insufficient_evidence" and early.members[0].state.traits == {}


def test_absence_is_read_sentence_by_sentence():
    people = [Entity(frozenset({"b"}), "character", "Brann"), Entity(frozenset({"m"}), "character", "Mira")]
    assert absentees(["Mira sat down. Brann and his sword were absent."], people) == {"Brann"}
    assert absentees(["Mira said Brann was brave."], people) == set()


@pytest.mark.integration
def test_scene_from_a_stored_consolidation(story):
    from app.providers.deterministic import RuleAdapter
    from app.services.reconstruction.context import scene
    from app.services.retrieval.consolidation import consolidate
    from tests.test_appearance_states import annotated_consolidation
    from tests.test_evidence_consolidation import gathered

    plan, expanded, _ = gathered(story, 3, "Arthur at dinner with Mira and Brann")
    derivation_id = consolidate(story.engine, plan, expanded, RuleAdapter(annotated_consolidation))
    story.db.expire_all()
    found, labels = scene(story.db, plan, derivation_id)
    assert labels[found.event] == "dinner"
    assert labels_of(found.members) == {"Arthur": "subject", "Élodie": "participant", "Mira": "participant",
                                        "brass compass": "object"}
    assert found.excluded["Brann"] == "absent from this scene"
    assert found.excluded["silver sword"] == "absent from this scene"
    # "Warm candlelight lit the room" never names the house, so the attribution gate refuses the lighting claim
    # and the setting stays unknown instead of being invented.
    from app.models.model_runs import Derivation
    assert story.db.get(Derivation, derivation_id).rejections["unattributed"] == 1
    assert (found.world, found.unknown) == ([], ["setting"])


def test_unexplained_inference_cannot_establish_scene_membership():
    from app.services.narrative.chronology import Chronology
    from app.services.reconstruction.scene import Entity, compose_scene
    from app.services.reconstruction.state import Fact
    arthur = Entity(frozenset({"arthur"}), "character", "Arthur")
    mira = Entity(frozenset({"mira"}), "character", "Mira")
    facts = [Fact("hair", "arthur", "hair", "chestnut", "scene", "explicit", "fact", "affirmed", frozenset({"dinner"})),
             Fact("bad", "mira", "held_object", "compass", "scene", "inferred", "fact", "negated",
                  frozenset({"dinner"}), " ")]
    result = compose_scene(facts, Chronology({"dinner": "fact"}, []), "dinner", arthur, [mira], {"arthur"}, [], set())
    assert [m.entity.label for m in result.members] == ["Arthur"]
