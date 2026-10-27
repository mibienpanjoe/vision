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
