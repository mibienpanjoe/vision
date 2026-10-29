"""Owner-scoped, reading-boundary-filtered entity browse views."""

import uuid
from collections import Counter, defaultdict

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.generations import SourceGeneration
from app.models.passages import Chapter
from app.models.works import Work
from app.schemas.entities import (
    AliasView,
    AnchorView,
    ConflictView,
    EntityDetail,
    EntityPage,
    EntitySummary,
    EventRelationView,
    EventView,
    FactView,
    MentionView,
    NarrativeScope,
    RelationView,
)
from app.schemas.scope import SourceSpan
from app.services.ingestion.upload import document_for
from app.services.narrative.eligibility import visible_narrative
from sqlalchemy import select

MAX_MENTIONS = 200


def not_found():
    return PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")


def not_ready():
    return PublicError(409, "NARRATIVE_NOT_READY", "Narrative extraction is not complete.")


def current_generation(db, actor, work_id):
    document = document_for(db, owned_object(db, Work, work_id, actor))
    generation = db.get(SourceGeneration, document.current_generation_id) if document.current_generation_id else None
    if generation is None:
        raise not_ready()
    return document, generation


def chapter_ordinal(db, document, generation, chapter_id) -> int | None:
    if chapter_id is None:
        return None
    chapter = db.scalar(select(Chapter).where(Chapter.id == chapter_id, Chapter.document_id == document.id,
                                             Chapter.parser_revision == generation.parser_revision))
    if chapter is None:
        raise not_found()
    return chapter.ordinal


def scoped(db, actor, work_id, chapter_id):
    document, generation = current_generation(db, actor, work_id)
    view = visible_narrative(db, generation, chapter_ordinal(db, document, generation, chapter_id))
    if view is None:
        raise not_ready()
    scope = NarrativeScope(generation_id=generation.id, parser_revision=generation.parser_revision,
                           through_chapter_id=chapter_id)
    return document, view, scope


def span(document, view, record) -> SourceSpan:
    return SourceSpan(document_revision_id=str(document.id), passage_id=str(record.passage_id), start=record.start,
                      end=record.end, quote=view.passages[record.passage_id][1][record.start:record.end])


def summary(document, view, entity_id, counts=None, aliases=None) -> EntitySummary:
    entity = view.entities[entity_id]
    return EntitySummary(id=entity.id, kind=entity.kind, label=view.labels[entity_id],
                         aliases=[AliasView(label=a.label, status=a.status, span=span(document, view, a))
                                  for a in (view.aliases if aliases is None else aliases[entity_id]) if a.entity_id == entity_id],
                         mention_count=counts[entity_id] if counts is not None else sum(entity_id in view.candidates[m.id] for m in view.mentions))


def list_entities(db, actor, work_id: uuid.UUID, chapter_id: uuid.UUID | None) -> EntityPage:
    document, view, scope = scoped(db, actor, work_id, chapter_id)
    counts = Counter(e for m in view.mentions for e in view.candidates[m.id])
    aliases = defaultdict(list)
    for alias in view.aliases:
        aliases[alias.entity_id].append(alias)
    items = sorted((summary(document, view, e, counts, aliases) for e in view.entities), key=lambda s: (s.label.casefold(), str(s.id)))
    return EntityPage(scope=scope, items=items)


def entity_detail(db, actor, work_id: uuid.UUID, entity_id: uuid.UUID, chapter_id: uuid.UUID | None) -> EntityDetail:
    document, view, scope = scoped(db, actor, work_id, chapter_id)
    if entity_id not in view.entities:
        raise not_found()
    mentions = [m for m in view.mentions if entity_id in view.candidates[m.id]]
    events = [e for e in view.events.values() if entity_id in view.participants.get(e.id, [])]
    event_ids = {e.id for e in events}
    facts = [f for f in view.facts.values() if f.subject_id == entity_id]
    fact_ids = {f.id for f in facts}
    return EntityDetail(
        scope=scope, entity=summary(document, view, entity_id),
        mentions=[MentionView(span=span(document, view, m), entity_id=m.entity_id, candidate_ids=view.candidates[m.id])
                  for m in mentions[:MAX_MENTIONS]],
        mentions_truncated=len(mentions) > MAX_MENTIONS,
        relations=[RelationView(subject_id=r.subject_id, relation=r.relation, object_id=r.object_id,
                                span=span(document, view, r))
                   for r in view.relations if entity_id in (r.subject_id, r.object_id)],
        events=[EventView(id=e.id, label=e.label, modality=e.modality,
                          evidence=[span(document, view, s) for s in view.event_evidence[e.id]],
                          participant_ids=sorted(view.participants.get(e.id, [])),
                          anchors=[AnchorView(kind=a.kind, value=a.value, span=span(document, view, a))
                                   for a in view.anchors if a.event_id == e.id])
                for e in events],
        event_relations=[EventRelationView(source_id=r.source_id, relation=r.relation, target_id=r.target_id,
                                           span=span(document, view, r))
                         for r in view.event_relations if r.source_id in event_ids and r.target_id in event_ids],
        facts=[FactView(id=f.id, attribute=f.attribute, value=f.value, kind=f.kind, support=f.support,
                        modality=f.modality, polarity=f.polarity, perspective=f.perspective, assumption=f.assumption,
                        canonical=f.canonical, evidence=[span(document, view, s) for s in view.fact_evidence[f.id]],
                        event_ids=view.fact_events[f.id])
               for f in facts],
        conflicts=[ConflictView(fact_ids=[c.fact_a_id, c.fact_b_id], status="unresolved")
                   for c in view.conflicts if c.fact_a_id in fact_ids or c.fact_b_id in fact_ids])
