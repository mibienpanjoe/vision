import json
import os
import re

import pytest
from app.models.entities import Entity, EntityAlias, EntityMention, EntityRelation
from app.models.model_runs import Derivation, ModelRun
from app.models.passages import Passage
from app.providers.local_entities import LocalEntities, extract
from app.services.narrative.entities import derive_entities
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.narrative_eval import evaluate
from tests.test_entity_extraction import generation  # noqa: F401


def recognizer(spans):
    """Fake span model: every listed surface wherever it occurs, longest first, without overlaps."""
    def recognize(texts):
        found = []
        for text in texts:
            taken, hits = set(), []
            for surface, label in sorted(spans, key=lambda s: -len(s[0])):
                for match in re.finditer(rf"\b{re.escape(surface)}\b", text):
                    if not taken & set(range(*match.span())):
                        taken |= set(range(*match.span()))
                        hits.append((*match.span(), label))
            found.append(sorted(hits))
        return found
    return recognize


def corefer_pronouns(name, pronouns=("he", "his", "I")):
    """Fake coreference: one cluster holding the first occurrence of `name` and every listed pronoun."""
    def corefer(text):
        first = re.search(rf"\b{name}\b", text)
        if not first:
            return []
        rest = [m.span() for p in pronouns for m in re.finditer(rf"\b{p}\b", text)]
        return [[first.span(), *rest]]
    return corefer


def no_coref(text):
    return []


def run(texts, spans, corefer=no_coref, known=()):
    sources = [{"ref": f"p{i}", "text": t} for i, t in enumerate(texts)]
    return extract(sources, list(known), recognizer(spans), corefer)


def labels(output):
    return sorted(e["label"] for e in output["entities"])


def test_full_names_fold_into_surnames_and_labels_never_split_a_name():
    output = run(["Henry Jekyll met Jekyll's butler. Harry Jekyll smiled. Hyde left; Hyde returned.",
                  "Sir Danvers Carew walked. Danvers Carew fell. Carew died. Danvers was mourned."],
                 [("Henry Jekyll", "character"), ("Jekyll", "character"), ("Harry Jekyll", "character"),
                  ("Hyde", "organization"), ("Danvers Carew", "character"), ("Carew", "place"),
                  ("Danvers", "character")])
    keys = {m["quote"]: m["entity"] for m in output["mentions"]}
    assert keys["Henry Jekyll"] == keys["Jekyll"] == keys["Harry Jekyll"]
    assert keys["Danvers Carew"] == keys["Carew"] == keys["Danvers"]
    assert len({m["entity"] for m in output["mentions"] if m["quote"] == "Hyde"}) == 1
    assert len(output["entities"]) == 3


def test_titles_alone_stay_ambiguous_and_stop_words_are_dropped():
    output = run(["Captain Mira and Captain Brann argued. The captain left. You will see."],
                 [("Captain Mira", "character"), ("Captain Brann", "character"), ("The captain", "character"),
                  ("You", "character"), ("will", "character")])
    captain = next(m for m in output["mentions"] if m["quote"] == "The captain")
    assert captain["entity"] is None and len(captain["candidates"]) == 2
    assert labels(output) == ["Captain Brann", "Captain Mira"]


def test_coreference_resolves_only_single_identity_clusters_with_exact_offsets():
    text = "Arthur ran. Then he stopped, and he waited."
    output = run([text], [("Arthur", "character")], corefer_pronouns("Arthur"))
    pronouns = [m for m in output["mentions"] if m["quote"] == "he"]
    assert [m["start"] for m in pronouns] == [m.start() for m in re.finditer(r"\bhe\b", text)]
    assert {m["entity"] for m in pronouns} == {"e0"}

    def mixed(text):
        return [[(0, 6), (text.index("Mira"), text.index("Mira") + 4), (text.index(" he") + 1, text.index(" he") + 3)]]
    output = run(["Arthur and Mira met; he spoke."], [("Arthur", "character"), ("Mira", "character")], mixed)
    assert not any(m["quote"] == "he" for m in output["mentions"])


def test_explicit_reveals_link_named_identities_but_possessives_do_not():
    output = run(['Arthur opened the mask and said, "I was Wren at ten."',
                  "Only now were Wren and Arthur the same person? No: Wren and Arthur were the same person.",
                  "Utterson was Jekyll's friend."],
                 [("Arthur", "character"), ("Wren", "character"), ("Utterson", "character"), ("Jekyll", "character")],
                 corefer_pronouns("Arthur", ("I",)))
    quotes = [r["quote"] for r in output["relations"]]
    assert quotes == ["I was Wren", "Wren and Arthur were the same person"]
    assert {(a["label"], a["status"]) for a in output["aliases"]} == {("Wren", "supported")}


def test_later_chapters_reuse_earlier_keys_by_folded_label():
    known = [{"key": "k:0", "kind": "character", "label": "Henry Jekyll"},
             {"key": "k:1", "kind": "place", "label": "the house by the ash tree"}]
    output = run(["Jekyll entered the house."], [("Jekyll", "character"), ("the house", "place")], known=known)
    assert output["entities"] == []
    assert [m["entity"] for m in output["mentions"]] == ["k:0", "k:1"]


def test_adapter_reads_the_data_block_and_reports_no_provider_tokens():
    from app.providers.contracts import ProviderCall
    data = json.dumps({"sources": [{"ref": "p0", "text": "Mira smiled."},
                                   {"ref": "known-entities", "text": "[]"}]})
    call = ProviderCall(system="", data=data, output_schema={}, max_output_tokens=1, timeout_seconds=1)
    result = LocalEntities(recognizer([("Mira", "character")]), no_coref).complete(call)
    assert json.loads(result.output)["entities"] == [{"key": "e0", "kind": "character", "label": "Mira"}]
    assert (result.usage.input_tokens, result.usage.output_tokens) == (0, 0)


FIXTURE_SPANS = [("Arthur", "character"), ("Élodie", "character"), ("Captain Mira", "character"),
                 ("Captain Brann", "character"), ("Mira", "character"), ("Brann", "character"),
                 ("Wren", "character"), ("house by the ash tree", "place"), ("brass compass", "object"),
                 ("silver sword", "object"), ("captain", "character")]


@pytest.mark.integration
def test_local_derivation_publishes_grounded_offsets_and_lineage(database, generation):  # noqa: F811
    adapter = LocalEntities(recognizer(FIXTURE_SPANS), corefer_pronouns("Arthur"))
    derivation_id = derive_entities(database, generation, adapter)
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        assert derivation.status == "succeeded" and derivation.processing_version.endswith(f"/local/{adapter.model}")
        assert {r.provider for r in db.scalars(select(ModelRun).where(ModelRun.derivation_id == derivation_id))} == {"local"}
        for mention in db.scalars(select(EntityMention).where(EntityMention.derivation_id == derivation_id)):
            passage = db.get(Passage, mention.passage_id)
            assert passage.text[mention.start:mention.end].strip()
        he = [(db.get(Passage, m.passage_id).text, m.start) for m in db.scalars(
            select(EntityMention).where(EntityMention.derivation_id == derivation_id)) if m.end - m.start == 2]
        assert he and all(text[start:start + 2] == "he" for text, start in he)
        assert len({start for text, start in he if text == he[0][0]}) == sum(1 for t, _ in he if t == he[0][0])
        report = evaluate(db, derivation_id)
        assert (report["misses"], report["false_merges"], report["ambiguity_violations"]) == ([], [], [])
        reveal = db.scalars(select(EntityRelation).where(EntityRelation.derivation_id == derivation_id,
                                                         EntityRelation.relation == "same_as")).all()
        assert reveal and all(db.get(Passage, r.passage_id).chapter_ordinal == 5 for r in reveal)
        arthur = db.scalar(select(Entity).where(Entity.derivation_id == derivation_id, Entity.label == "Arthur"))
        assert "Wren" in {a.label for a in db.scalars(select(EntityAlias).where(EntityAlias.entity_id == arthur.id))}


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("VISION_LOCAL_MODELS") != "1",
                    reason="Set VISION_LOCAL_MODELS=1 to run the pinned local models (about 2 GB, CPU)")
def test_pinned_local_models_on_the_synthetic_fixture(database, generation):  # noqa: F811
    derivation_id = derive_entities(database, generation, LocalEntities())
    with Session(database) as db:
        derivation = db.get(Derivation, derivation_id)
        report = evaluate(db, derivation_id) if derivation.status == "succeeded" else None
        relations = [(db.get(Passage, r.passage_id).text[r.start:r.end]) for r in db.scalars(
            select(EntityRelation).where(EntityRelation.derivation_id == derivation_id))]
    print(json.dumps({"status": derivation.status, "rejections": derivation.rejections, "report": report,
                      "relations": relations}, ensure_ascii=False, indent=1))
    assert derivation.status == "succeeded"
    assert (report["misses"], report["false_merges"], report["splits"], report["ambiguity_violations"]) == (
        [], [], [], [])
    assert any("Wren" in quote and ("I was" in quote or "same person" in quote) for quote in relations)
