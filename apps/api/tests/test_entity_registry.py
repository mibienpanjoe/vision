"""References expose only selected, cutoff-visible, unambiguous identities."""

from types import SimpleNamespace
from uuid import UUID

from app.providers.consolidation import Consolidation
from app.services.narrative.eligibility import Narrative
from app.services.retrieval.entity_registry import canonicalize, registry


def test_refs_and_aliases_resolve_without_a_shared_title_or_future_entity():
    a, b, future = (UUID(int=n) for n in (1, 2, 3))
    view = Narrative({"p": (1, "Mira captain"), "other": (1, "Brann")},
                     entities={i: SimpleNamespace(label=label, kind="character") for i, label in
                               [(a, "Captain Mira"), (b, "Captain Brann"), (future, "Late Name")]},
                     labels={a: "Captain Mira", b: "Captain Brann", future: "Late Name"},
                     mentions=[SimpleNamespace(id="m", passage_id="p", start=0, end=4),
                               SimpleNamespace(id="title", passage_id="p", start=5, end=12)],
                     candidates={"m": {a}, "title": {a, b}})
    entries, names = registry(view, {"p"}, {a})
    assert all(e["label"] != "Late Name" for e in entries)
    assert names["mira"] == "Captain Mira" and "captain" not in names
    ref = next(e["ref"] for e in entries if e["label"] == "Captain Mira")
    output = Consolidation.model_validate({"facts": [{"subject": ref, "attribute": "held_object",
        "value": "brass compass", "kind": "scene", "support": "explicit", "modality": "fact",
        "events": ["dinner"], "evidence": [{"ref": "p0", "quote": "Mira held a brass compass."}]}]})
    assert canonicalize(output, names).facts[0].subject == "Captain Mira"
    assert output.facts[0].subject == ref  # normalized copy; captured raw output stays intact


def test_registry_never_exceeds_its_reserved_input_budget():
    entity_id = UUID(int=1)
    view = Narrative({}, entities={entity_id: SimpleNamespace(label="Mira", kind="character")},
                     labels={entity_id: "Mira"})
    assert registry(view, set(), {entity_id}, max_characters=0) == ([], {})


def test_pronouns_and_negated_phrases_are_not_name_aliases():
    entity_id = UUID(int=1)
    view = Narrative({"p": (1, "he Brann, not Arthur")},
                     entities={entity_id: SimpleNamespace(label="Brann", kind="character")},
                     labels={entity_id: "Brann"},
                     mentions=[SimpleNamespace(id="pronoun", passage_id="p", start=0, end=2),
                               SimpleNamespace(id="phrase", passage_id="p", start=3, end=20)],
                     candidates={"pronoun": {entity_id}, "phrase": {entity_id}})
    entries, names = registry(view, {"p"}, {entity_id})
    assert entries[0]["aliases"] == ["brann"]
    assert "he" not in names and "brann, not arthur" not in names
