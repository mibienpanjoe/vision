"""Query-scoped references and unique visible surfaces; shared titles never resolve."""

import json
import re
from collections import defaultdict

from app.services.retrieval.entity_lookup import PRONOUNS, fold


def registry(view, passage_ids, required, max_characters=4_000):
    selected = set(required) & view.entities.keys()
    surfaces = defaultdict(set)
    for mention in view.mentions:
        if mention.passage_id not in passage_ids:
            continue
        ids = view.candidates.get(mention.id, set())
        selected.update(ids)
        text = view.passages[mention.passage_id][1][mention.start:mention.end]
        name = fold(text).strip()
        if name not in PRONOUNS and not re.search(r"[,;.!?]|\bnot\b", name):
            surfaces[name].update(ids)
    for entity_id in selected:
        surfaces[fold(view.labels[entity_id])].add(entity_id)
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


def canonicalize(output, names):
    def resolve(name):
        return names.get(fold(name), name)
    return output.model_copy(update={
        "facts": [f.model_copy(update={"subject": resolve(f.subject)}) for f in output.facts],
        "events": [e.model_copy(update={"participants": [resolve(p) for p in e.participants]}) for e in output.events],
        "identity_links": [link.model_copy(update={"subject": resolve(link.subject), "object": resolve(link.object)})
                           for link in output.identity_links],
    })
