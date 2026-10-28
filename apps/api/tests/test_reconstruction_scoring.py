"""Counterexamples that the old word-overlap scorer misclassified."""

from copy import deepcopy

from tests.reconstruction_eval import DATA, evaluate


def score(case_id, attribute, values, *, label=None, status="canonical"):
    case = next(c for c in DATA["cases"] if c["id"] == case_id)
    labels = {"arthur": "Arthur", "house": "house by the ash tree", "compass": "brass compass"}
    member = {"entity": {"label": label or labels[case["subject"]]}, "unknown": [],
              "traits": [{"attribute": attribute, "values": values, "status": status, "evidence": []}]}
    body = {"outcome": "resolved", "data": {"subject": member, "participants": [], "world": []}}
    return evaluate(deepcopy(case), body, {})


def test_blue_hair_does_not_satisfy_a_blue_coat():
    assert "child-coat" in score("child-before-war", "hair_color", ["blue"])["missing"]


def test_one_word_of_a_multiword_value_is_not_complete_recall():
    assert "child-coat" in score("child-before-war", "coat_color", ["blue"])["missing"]


def test_material_does_not_assert_roof_condition():
    report = score("house-war", "roof_material", ["slate"])
    assert report["incorrect"] == [] and report["missing"] == ["roof-destroyed"]


def test_an_intact_roof_during_the_war_is_incorrect():
    assert score("house-war", "roof_condition", ["intact slate"])["incorrect"]


def test_wrong_subject_never_falls_back_to_the_primary_member():
    assert "child-coat" in score("child-before-war", "attire", ["blue wool coat"], label="Brann")["missing"]


def test_inference_is_not_counted_as_canonical():
    assert "child-coat" in score("child-before-war", "attire", ["blue wool coat"], status="inferred")["missing"]


def test_full_value_and_attribute_match_counts():
    assert "child-coat" not in score("child-before-war", "coat", ["blue wool coat"])["missing"]


def test_negated_value_does_not_satisfy_affirmed_trait():
    assert "child-coat" in score("child-before-war", "attire", ["not blue wool coat"])["missing"]


def test_explicit_compass_phrase_and_scene_attribute_are_a_complete_match():
    assert "home-compass" not in score("mira-dinner", "held_object_at_dinner", ["holding her brass compass"],
                                        label="Captain Mira")["missing"]


def test_left_cheek_in_the_complete_value_can_qualify_a_component_attribute():
    assert "home-scar" not in score("home-eye-conflict", "cheek_scar", ["left-cheek scar visible"])["missing"]
    assert "home-scar" in score("home-eye-conflict", "cheek_scar", ["right-cheek scar visible"])["missing"]


def test_worn_coat_attribute_keeps_complete_garment_matching():
    assert "child-coat" not in score("child-before-war", "coat_worn", ["blue wool coat"])["missing"]


def test_split_coat_properties_require_the_full_garment_description():
    case = next(c for c in DATA["cases"] if c["id"] == "child-before-war")
    traits = [{"attribute": "coat_color", "status": "canonical", "values": ["blue"], "evidence": []},
              {"attribute": "coat_material", "status": "canonical", "values": ["wool"], "evidence": []}]
    body = {"outcome": "resolved", "data": {"subject": {"entity": {"label": "Arthur"}, "traits": traits,
                                                       "unknown": []}, "participants": [], "world": []}}
    assert "child-coat" not in evaluate(case, body, {})["missing"]
    traits.pop()
    assert "child-coat" in evaluate(case, body, {})["missing"]


def test_scar_condition_and_complete_held_object_are_recognized():
    assert "home-scar" not in score("home-eye-conflict", "left_cheek_scar", ["visible"])["missing"]
    assert "home-compass" not in score("mira-dinner", "held", ["brass compass"], label="Captain Mira")["missing"]


def test_properties_of_different_garments_cannot_complete_one_coat():
    case = next(c for c in DATA["cases"] if c["id"] == "child-before-war")
    traits = [{"attribute": "coat_color", "status": "canonical", "values": ["blue"], "evidence": []},
              {"attribute": "shirt_material", "status": "canonical", "values": ["wool"], "evidence": []}]
    body = {"outcome": "resolved", "data": {"subject": {"entity": {"label": "Arthur"}, "traits": traits,
                                                       "unknown": []}, "participants": [], "world": []}}
    assert "child-coat" in evaluate(case, body, {})["missing"]
