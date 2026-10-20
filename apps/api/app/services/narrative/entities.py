"""Derive entities, exact mentions, aliases and relations for one source generation.

Every accepted item is grounded in an exact passage span; see `derivations` for
the claim and guarded publication shared with later stages.
"""

import uuid
from collections import Counter
from collections.abc import Callable

from app.models.entities import (
    Entity,
    EntityAlias,
    EntityMention,
    EntityRelation,
    MentionCandidate,
)
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.extraction import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    EntityExtraction,
    entity_request,
)
from app.services.narrative.derivations import ground, run_derivation

STAGE = "entities"


def derive_entities(engine, generation_id: uuid.UUID, adapter: ProviderAdapter, limits: Limits = Limits(),
                    cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    def build(group, _previous):
        return entity_request([SourceItem(ref=f"p{p.ordinal}", text=p.text) for p in group], limits)

    return run_derivation(engine, generation_id, STAGE, adapter, EntityExtraction, PROMPT_VERSION, limits,
                          build, publish, limits.max_input_chars - len(INSTRUCTIONS), cancelled=cancelled)


def publish(db, derivation_id, outputs) -> dict:
    """Write grounded items; returns rejection counts by reason (no text)."""
    rejected: Counter[str] = Counter()
    entities: dict[tuple[str, str], Entity] = {}
    staged = []
    for group, output, run_id in outputs:
        by_ref = {f"p{p.ordinal}": p for p in group}
        declared = {}
        for item in output.entities:
            if item.key in declared:
                rejected["duplicate_key"] += 1
            else:
                declared[item.key] = item
        used, mentions, seen = set(), [], set()
        for item in output.mentions:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            keys = list(dict.fromkeys(([item.entity] if item.entity else []) + item.candidates))
            if passage is None or span is None:
                rejected["ungrounded"] += 1
            elif not keys or any(key not in declared for key in keys):
                rejected["unknown_entity"] += 1
            elif (passage.id, span) in seen:
                rejected["duplicate_mention"] += 1
            else:
                seen.add((passage.id, span))
                used.update(keys)
                mentions.append((passage, span, item.entity, keys))
        for key in declared:
            if key not in used:
                rejected["unmentioned_entity"] += 1
        local = {}
        for key in used:
            item = declared[key]
            identity = (item.kind, item.label.casefold())
            if identity not in entities:
                entities[identity] = Entity(id=uuid.uuid4(), derivation_id=derivation_id, kind=item.kind, label=item.label)
            local[key] = entities[identity]
        staged.append((by_ref, output, run_id, local, mentions))
    db.add_all(entities.values())
    db.flush()
    for by_ref, output, run_id, local, mentions in staged:
        for passage, (start, end), resolved, keys in mentions:
            mention = EntityMention(id=uuid.uuid4(), derivation_id=derivation_id, passage_id=passage.id, start=start,
                                    end=end, entity_id=local[resolved].id if resolved else None, model_run_id=run_id)
            db.add(mention)
            db.flush()
            db.add_all(MentionCandidate(mention_id=mention.id, entity_id=eid)
                       for eid in dict.fromkeys(local[key].id for key in keys))
        for item in output.aliases:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            if span is None or item.label.casefold() not in item.quote.casefold():
                rejected["ungrounded"] += 1
            elif item.entity not in local:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityAlias(entity_id=local[item.entity].id, label=item.label, status=item.status,
                                   passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
        for item in output.relations:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            if span is None:
                rejected["ungrounded"] += 1
            elif item.subject not in local or item.object not in local or local[item.subject] is local[item.object]:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityRelation(derivation_id=derivation_id, subject_id=local[item.subject].id,
                                      relation=item.relation, object_id=local[item.object].id,
                                      passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
    return {reason: count for reason, count in rejected.items() if count}
