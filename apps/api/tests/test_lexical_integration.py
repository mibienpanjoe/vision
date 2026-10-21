import pytest
from app.models.generations import SourceGeneration
from app.models.passages import Passage
from app.services.narrative.eligibility import visible_narrative
from app.services.retrieval.entity_lookup import SubjectLookup
from app.services.retrieval.evidence import collect, source_span
from app.services.retrieval.lexical import (
    appearance_linked,
    entity_linked,
    lexical,
    terms,
)
from sqlalchemy import select

pytestmark = pytest.mark.integration


def scope(story, cutoff, query, **fields):
    plan = story.plan(cutoff, query=query, **fields)
    view = visible_narrative(story.db, story.db.get(SourceGeneration, plan.generation_id), plan.cutoff)
    return plan, view, SubjectLookup(view)


def texts(view, candidates):
    return [view.passages[c.passage_id][1][c.start:c.end] for c in candidates]


def chapters(view, candidates):
    return {view.passages[c.passage_id][0] for c in candidates}


def test_entity_and_description_links_respect_the_reading_boundary(story):
    plan, view, _ = scope(story, 2, "Arthur")
    linked = entity_linked(story.db, plan, view)
    assert linked and chapters(view, linked) <= {1, 2}
    for item in linked:
        passage = view.passages[item.passage_id][1]
        assert item.paths == {"entity": linked.index(item) + 1}
        assert {passage[s:e] for s, e in item.anchors} == {"Arthur"}
    described = appearance_linked(story.db, plan, view)
    quotes = texts(view, described)
    assert all(item.protected for item in described) and chapters(view, described) <= {1, 2}
    assert "At ten, Arthur had chestnut hair and an unmarked left cheek." in quotes
    assert "Ten years later, during the war, a blade cut Arthur's left cheek and left a scar." in quotes
    assert not any("linen" in q for q in quotes)
    whole_plan, whole_view, _ = scope(story, None, "Arthur")
    assert any("remembered Arthur at ten" in q for q in texts(whole_view, appearance_linked(story.db, whole_plan, whole_view)))


def test_names_are_unambiguous_visible_surfaces(story):
    _, _, early = scope(story, 2, "Arthur")
    arthur = early.find("arthur")[0].subjects[0]
    assert early.names(arthur) == ["arthur"]
    mira = early.find("mira")[0].subjects[0]
    assert early.names(mira) == ["captain mira", "mira"]
    _, _, late = scope(story, 5, "Arthur")
    assert late.names(late.find("arthur")[0].subjects[0]) == ["arthur", "wren"]


def test_full_text_finds_exact_names_and_phrases_within_scope(story):
    plan, view, lookup = scope(story, None, "Arthur at home after the war")
    assert terms(plan) == ["at home", "after the war"]
    ranked = lexical(story.db, plan, lookup.names(plan.subject), terms(plan))
    assert texts(view, ranked)[0] == "After the war, Arthur travelled home. The journey account did not describe his cheek or clothing."
    assert any("Arthur's coat" in t for t in texts(view, ranked))  # possessive punctuation
    assert len(texts(view, lexical(story.db, plan, ["steel armor"], []))) == 2
    assert lexical(story.db, plan, ["armor steel"], []) == []
    elodie = lexical(story.db, plan, ["élodie"], [])
    assert len(elodie) == 5 and all("Élodie" in t for t in texts(view, elodie))

    compass_plan, compass_view, _ = scope(story, 2, "brass compass")
    compass = lexical(story.db, compass_plan, ["brass compass"], [])
    assert texts(compass_view, compass) == ["Captain Mira carried a brass compass. Captain Brann carried a silver sword. "
                                            "A masked visitor called Wren watched them; nobody knew the visitor's name."]
    assert lexical(story.db, compass_plan, ["linen shirt"], []) == []


def test_candidates_never_cross_works_and_merge_by_exact_span(story):
    plan, view, lookup = scope(story, None, "Arthur")
    paths = [entity_linked(story.db, plan, view), appearance_linked(story.db, plan, view),
             lexical(story.db, plan, lookup.names(plan.subject), [])]
    other = set(story.db.scalars(select(Passage.id).where(Passage.document_id == story.other_document)))
    assert other and not any(c.passage_id in other for found in paths for c in found)
    merged = collect(*paths)
    assert len(merged) == len({c.key for found in paths for c in found})
    both = [c for c in merged if set(c.paths) == {"entity", "lexical"}]
    assert both and all(c.anchors for c in both)
    span = source_span(plan.document_id, view, next(c for c in merged if c.protected))
    span.validate_text(view.passages[__import__("uuid").UUID(span.passage_id)][1])
