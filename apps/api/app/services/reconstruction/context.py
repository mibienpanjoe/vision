"""Load one consolidation into claims and chronology, and compute a planned subject's state from it.

The requested moment is the event the consolidation anchored in quoted text,
recorded in its scope; an unanchored moment is never guessed from labels. With
no moment and no scene asked for, distinct moments become choices. Identity
links explicitly stated inside the consolidation extend the subject; inferred
links do not.
"""

import uuid

from app.models.entities import EntityRelation
from app.models.events import Event, EventParticipant, EventRelation
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.models.visual_facts import FactEvent, VisualFact
from app.services.narrative.chronology import Chronology, Statement
from app.services.narrative.eligibility import visible_narrative
from app.services.reconstruction.scene import Entity, Scene, absentees, compose_scene
from app.services.reconstruction.state import Fact, State, reconstruct
from app.services.retrieval.entity_lookup import SubjectLookup
from sqlalchemy import select


def claims(db, derivation_id: uuid.UUID) -> tuple[list[Fact], Chronology, dict]:
    events = {e.id: e for e in db.scalars(select(Event).where(Event.derivation_id == derivation_id))}
    linked: dict = {}
    for fact_id, event_id in db.execute(select(FactEvent.fact_id, FactEvent.event_id).join(VisualFact)
                                        .where(VisualFact.derivation_id == derivation_id)):
        linked.setdefault(fact_id, set()).add(event_id)
    facts = [Fact(f.id, f.subject_id, f.attribute, f.value, f.kind, f.support, f.modality, f.polarity,
                  frozenset(linked.get(f.id, ()))) for f in
             db.scalars(select(VisualFact).where(VisualFact.derivation_id == derivation_id))]
    statements = [Statement(r.source_id, r.relation, r.target_id) for r in
                  db.scalars(select(EventRelation).where(EventRelation.derivation_id == derivation_id))]
    return facts, Chronology({i: e.modality for i, e in events.items()}, statements), {i: e.label for i, e in events.items()}


def subject_group(db, derivation_id, entity_ids) -> set:
    group = set(entity_ids)
    for a, b in db.execute(select(EntityRelation.subject_id, EntityRelation.object_id).where(
            EntityRelation.derivation_id == derivation_id, EntityRelation.relation == "same_as")):
        if a in group or b in group:
            group |= {a, b}
    return group


def appearance(db, plan, derivation_id: uuid.UUID, subject=None) -> tuple[State, dict]:
    """The state of `subject` (default: the plan's subject) and the consolidation's event labels."""
    derivation = db.get(Derivation, derivation_id)
    if derivation is None or derivation.stage != "consolidation" or derivation.status != "succeeded" \
            or derivation.generation_id != plan.generation_id:
        raise ValueError("appearance requires a succeeded consolidation of the plan's generation")
    subject = subject or plan.subject
    facts, chronology, labels = claims(db, derivation_id)
    anchored = (derivation.scope or {}).get("requested_event")
    asked = plan.moment is not None or plan.context is not None
    if asked and anchored is None:
        return State("insufficient_evidence", None, unknown=["moment"]), labels
    event = uuid.UUID(anchored) if anchored else None
    return reconstruct(facts, subject_group(db, derivation_id, subject.entity_ids), subject.kind, event,
                       chronology), labels


def scene(db, plan, derivation_id: uuid.UUID) -> tuple[Scene | State, dict]:
    """The scene at the anchored event, or the subject's non-resolved state when no single event applies."""
    state, labels = appearance(db, plan, derivation_id)
    if state.outcome == "needs_context" or state.event is None:
        return state, labels
    derivation = db.get(Derivation, derivation_id)
    facts, chronology, _ = claims(db, derivation_id)
    view = visible_narrative(db, db.get(SourceGeneration, plan.generation_id), plan.cutoff)
    lookup = SubjectLookup(view)
    subjects = {lookup.subject(e) for e in view.entities}
    entities = {s: Entity(frozenset(s.entity_ids), s.kind, s.label) for s in subjects if s is not None}
    subject = entities[lookup.subject(plan.subject.entity_ids[0])]
    participants = set(db.scalars(select(EventParticipant.entity_id).where(EventParticipant.event_id == state.event)))
    carriers = {entities[lookup.subject(r.object_id)].label: entities[lookup.subject(r.subject_id)].label
                for r in view.relations if r.relation == "carries"}
    spans = (derivation.scope or {}).get("spans", [])
    texts = [p.text for p in db.scalars(select(Passage).where(Passage.id.in_({uuid.UUID(s[0]) for s in spans})))]
    present = [e for e in entities.values() if e is not subject]
    requested = [entities[lookup.subject(p.entity_ids[0])] for p in plan.participants]
    return compose_scene(facts, chronology, state.event, subject, present, participants, requested,
                         absentees(texts, list(entities.values())), carriers), labels
