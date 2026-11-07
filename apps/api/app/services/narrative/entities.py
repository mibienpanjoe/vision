"""Derive entities, exact mentions, aliases and relations for one source generation.

Every accepted item is grounded in an exact passage span; see `derivations` for
the claim and guarded publication shared with later stages.
"""

import json
import re
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
from app.providers.local_entities import full_name, is_name, person_evidence
from app.services.narrative.derivations import ground, run_derivation

STAGE = "entities"
KNOWN_BUDGET = 8_000


def known_listing(previous, text="") -> str:
    """Earlier groups' declared entities as `k:n` keys, in output order, within the budget."""
    listing, size = [], 2
    entries = list(enumerate(e for output in previous for e in output.entities))
    if text:
        import re
        entries.sort(key=lambda entry: not re.search(r"(?<!\w)" + re.escape(entry[1].label) + r"(?!\w)", text, re.I))
    for n, item in entries:
        entry = json.dumps({"key": f"k:{n}", "kind": item.kind, "label": item.label}, ensure_ascii=False)
        if size + len(entry) + 1 > KNOWN_BUDGET:
            break
        listing.append(entry)
        size += len(entry) + 1
    return f"[{','.join(listing)}]"


def derive_entities(engine, generation_id: uuid.UUID, adapter: ProviderAdapter, limits: Limits = Limits(),
                    cancelled: Callable[[], bool] = lambda: False, input_id=None) -> uuid.UUID:
    def build(group, previous):
        return entity_request([SourceItem(ref=f"p{p.ordinal}", text=p.text) for p in group],
                              known_listing(previous, "\n".join(p.text for p in group)) if previous else "", limits)

    return run_derivation(engine, generation_id, STAGE, adapter, EntityExtraction, PROMPT_VERSION, limits,
                          build, publish, limits.max_input_chars - len(INSTRUCTIONS) - KNOWN_BUDGET,
                          cancelled=cancelled, input_id=input_id)


def publish(db, derivation_id, outputs) -> dict:
    """Write grounded items; returns rejection counts by reason (no text)."""
    rejected: Counter[str] = Counter()
    entities: dict[tuple[str, str], Entity] = {}
    earlier: list = []  # declarations from previous groups, addressed as k:n
    staged = []
    for group, output, run_id in outputs:
        by_ref = {f"p{p.ordinal}": p for p in group}
        declared = {f"k:{n}": item for n, item in enumerate(earlier)}
        for item in output.entities:
            if item.key in declared:
                rejected["duplicate_key"] += 1
            else:
                declared[item.key] = item
        earlier.extend(output.entities)
        used, mentions, seen = set(), [], set()
        for item in output.mentions:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote, item.start) if passage else None
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
            if key not in used and not key.startswith("k:"):
                rejected["unmentioned_entity"] += 1
        local = {}
        for key in used:
            item = declared[key]
            identity = (item.kind, item.label.casefold())
            if identity not in entities:
                entities[identity] = Entity(id=uuid.uuid4(), derivation_id=derivation_id, kind=item.kind, label=item.label)
            local[key] = entities[identity]
        staged.append((by_ref, output, run_id, local, mentions))
    for by_ref, output, _, local, _ in staged:
        for relation in output.relations:
            passage = by_ref.get(relation.ref)
            if (relation.relation == "same_as" and relation.subject in local and relation.object in local
                    and passage is not None and ground(passage, relation.quote, relation.start)
                    and re.search(r"\b(?:were|are) the same (?:person|man|woman)\b", relation.quote, re.I)):
                local[relation.subject].kind = local[relation.object].kind = "character"
    for _, _, _, local, mentions in staged:
        for passage, (start, end), resolved, _ in mentions:
            if resolved in local and is_name(passage.text[start:end]) and person_evidence(passage.text, start, end):
                local[resolved].kind = "character"
    canonical, replacements = {}, {}
    for entity in entities.values():
        replacements[entity.id] = canonical.setdefault((entity.kind, entity.label.casefold()), entity)
    for _, _, _, local, _ in staged:
        local.update({key: replacements[entity.id] for key, entity in local.items()})
    entities = canonical
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
            span = ground(passage, item.quote, item.start) if passage else None
            if span is None or item.label.casefold() not in item.quote.casefold():
                rejected["ungrounded"] += 1
            elif item.entity not in local:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityAlias(entity_id=local[item.entity].id, label=item.label, status=item.status,
                                   passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
        for item in output.relations:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote, item.start) if passage else None
            if span is None:
                rejected["ungrounded"] += 1
            elif item.subject not in local or item.object not in local or local[item.subject] is local[item.object]:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityRelation(derivation_id=derivation_id, subject_id=local[item.subject].id,
                                      relation=item.relation, object_id=local[item.object].id,
                                      passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
    link_name_variants(db, derivation_id, entities.values(), staged)
    return {reason: count for reason, count in rejected.items() if count}


def link_name_variants(db, derivation_id, entities, staged):
    """Keep named rows immutable; a full-name citation links an unambiguous component."""
    import re

    entities = list(entities)
    by_id = {entity.id: entity for entity in entities}
    for short_id, full_id in name_variants(entities):
        short = by_id[short_id]
        for _, _, run_id, local, mentions in staged:
            grounded = next(((p, a, b) for p, (a, b), resolved, _ in mentions
                             if resolved in local and local[resolved].id == full_id
                             and short.label.casefold() in p.text[a:b].casefold()
                             and not re.search(r"\b(different people|another|unrelated|not the same)\b", p.text, re.I)), None)
            if grounded:
                passage, start, end = grounded
                db.add(EntityRelation(derivation_id=derivation_id, subject_id=short.id, relation="same_as",
                                      object_id=full_id, passage_id=passage.id, start=start, end=end, model_run_id=run_id))
                db.add(EntityAlias(entity_id=full_id, label=short.label, status="supported",
                                   passage_id=passage.id, start=start, end=end, model_run_id=run_id))
                break


def name_variants(entities):
    """Decide component uniqueness over the complete derivation, including competing kinds."""
    from app.providers.local_entities import PREPOSITIONS, name_key

    named = [entity for entity in entities if is_name(entity.label)]
    components = {}
    for entity in named:
        words = name_key(entity.label).split()
        if full_name(entity.label):
            components.setdefault(words[0], set()).add(entity.id)
            if not set(words) & PREPOSITIONS:
                components.setdefault(words[-1], set()).add(entity.id)
    by_id = {entity.id: entity for entity in named}
    for short in named:
        matches = components.get(name_key(short.label), set())
        if short.kind == "character" and len(matches) == 1:
            full_id = next(iter(matches))
            if full_id != short.id and by_id[full_id].kind == "character":
                yield short.id, full_id
