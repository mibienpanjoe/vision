"""Moment-free base portraits keep stable identity traits and never blend changing states."""
from app.services.reconstruction.state import Fact, base_state

S = "arthur"


def fact(i, attribute, value, kind="identity", events=(), support="explicit", polarity="affirmed", modality="fact"):
    return Fact(i, S, attribute, value, kind, support, modality, polarity, frozenset(events))


def test_untimed_and_repeated_identity_traits_are_canonical():
    state = base_state([fact(1, "eyes", "grey"), fact(2, "hair", "black", events={"e1"}),
                        fact(3, "hair", "black", events={"e2"})], {S}, "character")
    assert state.outcome == "resolved"
    assert {k: (t.status, t.values) for k, t in state.traits.items()} == {
        "eyes": ("canonical", ["grey"]), "hair": ("canonical", ["black"])}
    assert state.unknown == ["attire"]


def test_one_absent_trait_does_not_discard_others():
    state = base_state([fact(1, "eyes", "grey")], {S}, "character")
    assert state.outcome == "resolved" and list(state.traits) == ["eyes"] and set(state.unknown) == {"hair", "attire"}


def test_changing_states_ages_and_scenes_are_never_blended():
    state = base_state([
        fact(1, "eyes", "grey"),
        fact(2, "hair", "chestnut", events={"child"}), fact(3, "hair", "white", events={"old"}),
        fact(4, "attire", "plain linen shirt", kind="scene", events={"home"}),
        fact(5, "left_cheek_scar", "fresh scar", kind="acquired", events={"war"}),
        fact(6, "age", "seven", events={"child"}),
    ], {S}, "character")
    assert list(state.traits) == ["eyes", "age"]
    assert state.traits["age"].status == "inferred"
    assert state.excluded[2] == state.excluded[3] == "differs between moments"
    assert state.excluded[4] == state.excluded[5] == "changes between moments"


def test_no_stable_evidence_is_not_a_base_portrait():
    state = base_state([fact(1, "hair", "chestnut", events={"child"}), fact(2, "attire", "coat", kind="scene")], {S}, "character")
    assert state.outcome == "insufficient_evidence"


def test_negated_or_unexplained_identity_does_not_enter():
    state = base_state([fact(1, "eyes", "grey"), fact(2, "eyes", "grey", polarity="negated"),
                        fact(3, "hair", "black", support="inferred")], {S}, "character")
    assert state.outcome == "insufficient_evidence"
    assert state.excluded[1] == "removed" and state.excluded[3] == "missing_assumption"
