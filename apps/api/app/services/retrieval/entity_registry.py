"""Query-scoped references and unique visible surfaces; shared titles never resolve."""

import json
import re
from collections import Counter, defaultdict

from app.services.retrieval.entity_lookup import PRONOUNS, fold


def registry(view, passage_ids, required, max_characters=4_000):
    selected = set(required) & view.entities.keys()
    surfaces = defaultdict(set)
    for mention in view.mentions:
        ids = view.candidates.get(mention.id, set())
        if mention.passage_id in passage_ids:
            selected.update(ids)
        text = view.passages[mention.passage_id][1][mention.start:mention.end]
        name = fold(text).strip()
        if name not in PRONOUNS and not re.search(r"[,;.!?]|\bnot\b", name):
            surfaces[name].update(ids)
    for entity_id, label in view.labels.items():
        surfaces[fold(label)].add(entity_id)
    for alias in view.aliases:
        surfaces[fold(alias.label)].add(alias.entity_id)
    entries, names, used = [], {}, 2
    ordered = sorted(selected, key=lambda e: (e not in required, fold(view.labels[e]), str(e)))
    for i, entity_id in enumerate(ordered):
        aliases = sorted(name for name, ids in surfaces.items() if ids == {entity_id} and len(name) <= 256)[:8]
        ref = f"entity:{i}"
        entry = {"ref": ref, "label": view.labels[entity_id],
                 "kind": view.entities[entity_id].kind, "aliases": aliases}
        size = len(json.dumps(entry, ensure_ascii=False)) + 2
        if used + size > max_characters:
            continue
        used += size
        entries.append(entry)
        canonical = view.entities[entity_id].label
        names[ref] = canonical
        names.update({name: canonical for name in aliases})
    return entries, names


def canonicalize(output, names, rejected=None):
    rejected = Counter() if rejected is None else rejected
    def resolve(name, reason):
        result = names.get(fold(name))
        if result is None:
            rejected[reason] += 1
        return result
    facts, events, links = [], [], []
    for fact in output.facts:
        subject = resolve(fact.subject, "unknown_subject")
        if subject is not None:
            facts.append(fact.model_copy(update={"subject": subject}))
    for event in output.events:
        participants = [value for name in event.participants
                        if (value := resolve(name, "unknown_participant")) is not None]
        events.append(event.model_copy(update={"participants": participants}))
    for link in output.identity_links:
        subject, target = resolve(link.subject, "unknown_entity"), resolve(link.object, "unknown_entity")
        if subject is not None and target is not None:
            links.append(link.model_copy(update={"subject": subject, "object": target}))
    return output.model_copy(update={"facts": facts, "events": events, "identity_links": links})
