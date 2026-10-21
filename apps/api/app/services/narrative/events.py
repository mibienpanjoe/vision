"""Derive events, evidence, participants, anchors and stated temporal relations.

Events depend on one succeeded entity derivation of the same generation; that
derivation is recorded as the input so a changed entity set adds a new event
derivation. Participants map to entities by exact label only, so a later alias
cannot silently attach an earlier event to a revealed identity.
"""

import json
import uuid
from collections import Counter
from collections.abc import Callable

from app.models.entities import Entity
from app.models.events import (
    Event,
    EventEvidence,
    EventParticipant,
    EventRelation,
    TemporalAnchor,
)
from app.models.model_runs import Derivation
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.events import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    EventExtraction,
    event_request,
)
from app.services.narrative.chronology import Chronology, Statement
from app.services.narrative.derivations import ground, run_derivation
from sqlalchemy import select
from sqlalchemy.orm import Session

STAGE = "events"
# Room left in the input budget for the earlier-chapter event list.
KNOWN_BUDGET = 8_000


def known_events(previous) -> list[tuple[str, object]]:
    """Global `k:n` keys for every event declared by earlier groups, in output order."""
    return [(f"k:{i}", event) for i, event in enumerate(e for output in previous for e in output.events)]


def known_listing(previous) -> str:
    listing, size = [], 2
    for key, event in known_events(previous):
        entry = json.dumps({"key": key, "label": event.label, "modality": event.modality}, ensure_ascii=False)
        if size + len(entry) + 1 > KNOWN_BUDGET:
            break
        listing.append(entry)
        size += len(entry) + 1
    return f"[{','.join(listing)}]"


def chronology(db, derivation_id) -> Chronology:
    modality = dict(db.execute(select(Event.id, Event.modality).where(Event.derivation_id == derivation_id)).all())
    statements = [Statement(r.source_id, r.relation, r.target_id)
                  for r in db.scalars(select(EventRelation).where(EventRelation.derivation_id == derivation_id))]
    return Chronology(modality, statements)


def derive_events(engine, generation_id: uuid.UUID, entity_derivation_id: uuid.UUID, adapter: ProviderAdapter,
                  limits: Limits = Limits(), cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    with Session(engine) as db:
        entities = db.get(Derivation, entity_derivation_id)
        if entities is None or entities.generation_id != uuid.UUID(str(generation_id)) or entities.stage != "entities" \
                or entities.status != "succeeded":
            raise ValueError("events require a succeeded entity derivation of the same generation")

    def build(group, previous):
        return event_request([SourceItem(ref=f"p{p.ordinal}", text=p.text) for p in group],
                             known_listing(previous) if previous else "", limits)

    def publish(db, derivation_id, outputs):
        return publish_events(db, derivation_id, entity_derivation_id, outputs)

    return run_derivation(engine, generation_id, STAGE, adapter, EventExtraction, PROMPT_VERSION, limits, build,
                          publish, limits.max_input_chars - len(INSTRUCTIONS) - KNOWN_BUDGET,
                          input_id=entity_derivation_id, cancelled=cancelled)


def publish_events(db, derivation_id, entity_derivation_id, outputs) -> dict:
    rejected: Counter[str] = Counter()
    names = {e.label.casefold(): e.id for e in db.scalars(select(Entity).where(Entity.derivation_id == entity_derivation_id))}
    global_events: list[Event | None] = []
    for group, output, run_id in outputs:
        by_ref = {f"p{p.ordinal}": p for p in group}
        local: dict[str, Event | None] = {}
        for item in output.events:
            spans = [(by_ref[e.ref], ground(by_ref[e.ref], e.quote)) for e in item.evidence if e.ref in by_ref]
            spans = [(p, s) for p, s in spans if s is not None]
            rejected["ungrounded"] += len(item.evidence) - len(spans)
            event = None
            if item.key in local:
                rejected["duplicate_key"] += 1
            elif spans:
                event = Event(id=uuid.uuid4(), derivation_id=derivation_id, label=item.label, modality=item.modality)
                db.add(event)
                db.flush()
                db.add_all(EventEvidence(event_id=event.id, passage_id=p.id, start=s[0], end=s[1], model_run_id=run_id)
                           for p, s in dict.fromkeys(spans))
                for name in dict.fromkeys(n.casefold() for n in item.participants):
                    if name in names:
                        db.add(EventParticipant(event_id=event.id, entity_id=names[name]))
                    else:
                        rejected["unknown_participant"] += 1
            else:
                rejected["unmentioned_event"] += 1
            local.setdefault(item.key, event)
            global_events.append(event)
        earlier = len(global_events) - len(output.events)

        def resolve(key):
            if key.startswith("k:"):
                index = int(key[2:])
                return global_events[index] if index < earlier else None
            return local.get(key)

        for item in output.anchors:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            event = resolve(item.event)
            if span is None:
                rejected["ungrounded"] += 1
            elif event is None:
                rejected["unknown_event"] += 1
            else:
                db.add(TemporalAnchor(event_id=event.id, kind=item.kind, value=item.value, passage_id=passage.id,
                                      start=span[0], end=span[1], model_run_id=run_id))
        for item in output.relations:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            source, target = resolve(item.source), resolve(item.target)
            if span is None:
                rejected["ungrounded"] += 1
            elif source is None or target is None or source is target:
                rejected["unknown_event"] += 1
            else:
                db.add(EventRelation(derivation_id=derivation_id, source_id=source.id, relation=item.relation,
                                     target_id=target.id, passage_id=passage.id, start=span[0], end=span[1],
                                     model_run_id=run_id))
    return {reason: count for reason, count in rejected.items() if count}
