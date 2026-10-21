import unicodedata
import uuid

import pytest
from app.core.errors import PublicError
from app.services.retrieval.query_plan import (
    InsufficientEvidence,
    NeedsContext,
    QueryPlan,
)
from pydantic import ValidationError
from tests.conftest import visualization_request as request


def test_request_shape_requires_a_subject_and_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        request(creative_mode="canon_first")
    with pytest.raises(ValidationError):
        request(query="Arthur", story_event_id="later-event")
    with pytest.raises(ValidationError):
        request(query="Arthur", moment={"kind": "age", "years": -1})


def subjects(outcome):
    assert isinstance(outcome, NeedsContext), outcome
    return sorted(c.label for c in outcome.choices if c.field == "subject")


@pytest.mark.integration
def test_source_boundary_story_age_and_scene_context_stay_distinct(story):
    plan, ids, chapters = story.plan, story.ids, story.chapters
    home = plan(3, query="Arthur at home after the war")
    assert isinstance(home, QueryPlan)
    assert (home.subject.label, home.subject.entity_ids) == ("Arthur", (ids["Arthur"],))
    assert (home.cutoff, home.cutoff_chapter_id, home.source_focus) == (3, chapters[3], None)
    assert (home.moment.kind, home.moment.text, home.context) == ("phrase", "after the war", "at home")

    child = plan(query="Arthur at ten in chapter 1")
    assert (child.moment.kind, child.moment.years, child.source_focus, child.cutoff) == ("age", 10, 1, None)
    assert child.context is None
    assert plan(query="When he was ten, Arthur").moment.years == 10

    narrowed = plan(4, query="Arthur through chapter 2")
    assert (narrowed.cutoff, narrowed.cutoff_chapter_id, narrowed.moment) == (2, chapters[2], None)
    assert plan(query="Arthur before chapter 3").cutoff == 2
    assert plan(query="Arthur", moment={"kind": "age", "years": 10}).moment.years == 10
    unspecified = plan(query="Arthur", creative_mode="interpretation", style="sepia ink wash")
    assert (unspecified.moment, unspecified.context, unspecified.creative_mode) == (None, None, "interpretation")


@pytest.mark.integration
def test_chapter_references_never_widen_the_reading_boundary(story):
    plan = story.plan
    for query in ("Arthur in chapter 4", "Arthur through chapter 3"):
        assert plan(2, query=query) == InsufficientEvidence(("The requested chapter is beyond the reading boundary.",))
    assert plan(query="Arthur in chapter 9") == InsufficientEvidence(("The request names a chapter this work does not have.",))
    assert isinstance(plan(query="Arthur before chapter 1"), InsufficientEvidence)


@pytest.mark.integration
def test_title_only_subjects_offer_eligible_candidates_without_merging(story):
    plan, ids = story.plan, story.ids
    for cutoff in (1, 2, None):
        outcome = plan(cutoff, query="the captain during the war")
        assert subjects(outcome) == ["Brann (character)", "Mira (character)"]
        assert {c.value for c in outcome.choices} == {str(ids["Mira"]), str(ids["Brann"])}
    chosen = plan(2, query="the captain during the war", entity_id=str(ids["Mira"]))
    assert (chosen.subject.label, chosen.moment.text) == ("Mira", "during the war")
    assert plan(2, query="the dragon at dawn") == InsufficientEvidence(
        ("No eligible character, place or object matches the request.",))


@pytest.mark.integration
def test_identity_reveals_apply_only_once_the_reader_reaches_them(story):
    plan, ids = story.plan, story.ids
    early = plan(2, query="Wren")
    assert (early.subject.label, early.subject.entity_ids) == ("Wren", (ids["Wren"],))
    assert subjects(plan(2, query="Wren", entity_id=str(ids["Arthur"]))) == ["Arthur (character)", "Wren (character)"]
    for cutoff in (5, None):
        late = plan(cutoff, query="Wren", entity_id=str(ids["Arthur"]))
        assert (late.subject.label, set(late.subject.entity_ids)) == ("Arthur", {ids["Arthur"], ids["Wren"]})
        assert plan(cutoff, query="Wren").subject == late.subject


@pytest.mark.integration
def test_structured_fields_and_query_text_conflicts_return_choices(story):
    plan, ids = story.plan, story.ids
    assert subjects(plan(3, query="Mira at dinner", entity_id=str(ids["Arthur"]))) == [
        "Arthur (character)", "Mira (character)"]
    moment = plan(3, query="Arthur after the war", moment={"kind": "age", "years": 10})
    assert [(c.field, c.value, c.label) for c in moment.choices] == [
        ("moment", "request", "age 10"), ("moment", "query-1", "after the war")]
    context = plan(3, query="Arthur at home", context="in battle")
    assert [(c.field, c.label) for c in context.choices] == [("context", "in battle"), ("context", "at home")]
    agreeing = plan(3, query="Arthur at ten at home", entity_id=str(ids["Arthur"]),
                    moment={"kind": "age", "years": 10}, context="AT HOME")
    assert (agreeing.moment.years, agreeing.context) == (10, "AT HOME")


@pytest.mark.integration
def test_scene_participants_and_decomposed_names_resolve_to_visible_identities(story):
    plan = story.plan
    query = unicodedata.normalize("NFD", "Arthur and Élodie at dinner with Mira")
    scene = plan(3, query=query)
    assert scene.subject.label == "Arthur"
    assert [p.label for p in scene.participants] == ["Élodie", "Mira"]
    assert scene.context == "at dinner"
    house = plan(1, query="the house by the ash tree before the war")
    assert (house.subject.kind, house.moment.text) == ("place", "before the war")
    assert plan(1, query="brass compass").subject.kind == "object"


@pytest.mark.integration
def test_other_owners_and_hidden_entities_get_the_safe_not_found(story):
    plan = story.plan
    with pytest.raises(PublicError) as stranger:
        plan(query="Arthur", actor="stranger")
    assert (stranger.value.status, stranger.value.code) == (404, "RESOURCE_NOT_FOUND")
    with pytest.raises(PublicError) as unknown:
        plan(query="Arthur", entity_id=str(uuid.uuid4()))
    assert unknown.value.status == 404
