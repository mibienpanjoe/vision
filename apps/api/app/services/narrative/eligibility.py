"""Reading-boundary visibility for derived records by dependency closure.

A record is visible only when every source span it depends on lies within the
cutoff and every derived record it depends on is itself visible. A later alias,
identity link, event or fact therefore cannot leak through an earlier citation.
"""

import uuid
from dataclasses import dataclass, field

from app.models.entities import (
    Entity,
    EntityAlias,
    EntityMention,
    EntityRelation,
    MentionCandidate,
)
from app.models.events import (
    Event,
    EventEvidence,
    EventParticipant,
    EventRelation,
    TemporalAnchor,
)
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.models.visual_facts import FactConflict, FactEvent, FactEvidence, VisualFact
from sqlalchemy import select


def latest(db, generation_id, stage, input_id=None):
    query = select(Derivation).where(Derivation.generation_id == generation_id, Derivation.stage == stage,
                                     Derivation.status == "succeeded")
    if input_id is not None:
        query = query.where(Derivation.input_derivation_id == input_id)
    return db.scalar(query.order_by(Derivation.completed_at.desc(), Derivation.id).limit(1))


@dataclass
class Narrative:
    """The derived records of one generation that a reader at `cutoff` may see."""
    passages: dict
    entities: dict = field(default_factory=dict)
    labels: dict = field(default_factory=dict)
    mentions: list = field(default_factory=list)
    candidates: dict = field(default_factory=dict)
    aliases: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    events: dict = field(default_factory=dict)
    event_evidence: dict = field(default_factory=dict)
    participants: dict = field(default_factory=dict)
    anchors: list = field(default_factory=list)
    event_relations: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    fact_evidence: dict = field(default_factory=dict)
    fact_events: dict = field(default_factory=dict)
    conflicts: list = field(default_factory=list)


def visible_narrative(db, generation, cutoff: int | None) -> Narrative | None:
    """None when no entity derivation has succeeded for the generation."""
    rows = db.execute(select(Passage.id, Passage.chapter_ordinal, Passage.text).where(
        Passage.document_id == generation.document_id, Passage.parser_revision == generation.parser_revision)).all()
    passages = {pid: (chapter, text) for pid, chapter, text in rows
                if cutoff is None or (chapter or 0) <= cutoff}

    def eligible(span) -> bool:
        return span.passage_id in passages

    entity_derivation = latest(db, generation.id, "entities")
    if entity_derivation is None:
        return None
    view = Narrative(passages)
    all_entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.derivation_id == entity_derivation.id))}
    candidate_rows = db.execute(select(MentionCandidate.mention_id, MentionCandidate.entity_id).join(EntityMention)
                                .where(EntityMention.derivation_id == entity_derivation.id)).all()
    by_mention: dict[uuid.UUID, set] = {}
    for mention_id, entity_id in candidate_rows:
        by_mention.setdefault(mention_id, set()).add(entity_id)
    for mention in db.scalars(select(EntityMention).where(EntityMention.derivation_id == entity_derivation.id)
                              .order_by(EntityMention.passage_id, EntityMention.start)):
        if eligible(mention):
            view.mentions.append(mention)
            for entity_id in by_mention.get(mention.id, set()):
                view.entities[entity_id] = all_entities[entity_id]
    for mention in view.mentions:
        view.candidates[mention.id] = sorted(by_mention.get(mention.id, set()) & view.entities.keys())
    for entity_id, entity in view.entities.items():
        texts = [passages[m.passage_id][1][m.start:m.end] for m in view.mentions if entity_id in by_mention.get(m.id, ())]
        # The stored label may come from a later batch; show it only if an eligible mention uses it.
        view.labels[entity_id] = entity.label if any(t.casefold() == entity.label.casefold() for t in texts) else texts[0]
    view.aliases = [a for a in db.scalars(select(EntityAlias).where(EntityAlias.entity_id.in_(view.entities)))
                    if eligible(a)]
    view.relations = [r for r in db.scalars(select(EntityRelation).where(EntityRelation.derivation_id == entity_derivation.id))
                      if eligible(r) and r.subject_id in view.entities and r.object_id in view.entities]

    event_derivation = latest(db, generation.id, "events", entity_derivation.id)
    if event_derivation is None:
        return view
    evidence: dict[uuid.UUID, list] = {}
    for item in db.scalars(select(EventEvidence).join(Event).where(Event.derivation_id == event_derivation.id)):
        evidence.setdefault(item.event_id, []).append(item)
    for event in db.scalars(select(Event).where(Event.derivation_id == event_derivation.id)):
        spans = evidence.get(event.id, [])
        if spans and all(eligible(s) for s in spans):
            view.events[event.id], view.event_evidence[event.id] = event, spans
    for event_id, entity_id in db.execute(select(EventParticipant.event_id, EventParticipant.entity_id)
                                          .where(EventParticipant.event_id.in_(view.events))):
        if entity_id in view.entities:
            view.participants.setdefault(event_id, []).append(entity_id)
    view.anchors = [a for a in db.scalars(select(TemporalAnchor).where(TemporalAnchor.event_id.in_(view.events)))
                    if eligible(a)]
    view.event_relations = [r for r in db.scalars(select(EventRelation)
                                                  .where(EventRelation.derivation_id == event_derivation.id))
                            if eligible(r) and r.source_id in view.events and r.target_id in view.events]

    fact_derivation = latest(db, generation.id, "facts", event_derivation.id)
    if fact_derivation is None:
        return view
    fact_spans: dict[uuid.UUID, list] = {}
    for item in db.scalars(select(FactEvidence).join(VisualFact).where(VisualFact.derivation_id == fact_derivation.id)):
        fact_spans.setdefault(item.fact_id, []).append(item)
    linked: dict[uuid.UUID, set] = {}
    for fact_id, event_id in db.execute(select(FactEvent.fact_id, FactEvent.event_id).join(VisualFact)
                                        .where(VisualFact.derivation_id == fact_derivation.id)):
        linked.setdefault(fact_id, set()).add(event_id)
    for fact in db.scalars(select(VisualFact).where(VisualFact.derivation_id == fact_derivation.id)):
        spans, events = fact_spans.get(fact.id, []), linked.get(fact.id, set())
        if spans and all(eligible(s) for s in spans) and fact.subject_id in view.entities and events <= view.events.keys():
            view.facts[fact.id], view.fact_evidence[fact.id], view.fact_events[fact.id] = fact, spans, sorted(events)
    view.conflicts = [c for c in db.scalars(select(FactConflict).where(FactConflict.derivation_id == fact_derivation.id))
                      if c.fact_a_id in view.facts and c.fact_b_id in view.facts]
    return view
