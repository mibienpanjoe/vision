"""On-device entity extraction (DEC-37/DEC-38) behind the entity-extraction contract.

GLiNER2 finds name and noun spans, fastcoref links pronouns within the batch
(one chapter, or a window of one), and versioned deterministic rules decide
identity. The output is the same `EntityExtraction` an LLM returns, with exact
start offsets, so grounding, `k:n` continuity, publication and run lineage are
shared with the provider path. No text leaves the machine.
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from functools import cache

from app.providers.contracts import ProviderCall, ProviderResult, Usage
from app.providers.extraction import KNOWN_REF

RULES_VERSION = "rules-v2"
GLINER = ("fastino/gliner2-base-v1", "f9634218e53580c56edf0de97ca1a7d3f1c2354e")
COREF = ("biu-nlp/f-coref", "e91dfff12879495d882ba9460d0c5d5dd44ade59")
LABELS = {"character": "a person or creature in the story, named or described",
          "place": "a location, building, room or landscape",
          "object": "a physical object, item, garment or weapon",
          "organization": "a group, institution or company"}
TITLES = {"captain", "mr", "mr.", "mrs", "mrs.", "dr", "dr.", "miss", "sir", "lady", "lord", "master", "inspector"}
DETERMINERS = {"the", "a", "an", "his", "her", "their", "its", "my", "our", "your"}
PREPOSITIONS = {"by", "of", "with", "in", "on", "at", "near", "from", "under"}
# Pronouns and function words a span model sometimes tags as names.
STOP = {"i", "me", "my", "he", "him", "his", "she", "her", "hers", "they", "them", "their", "it", "its",
        "you", "your", "yours", "we", "us", "our", "will", "shall", "one", "street"}
# Text between two resolved identities that states they are the same.
REVEAL_BETWEEN = re.compile(r"^(?:,?\s*who\s+(?:was|is)\s+(?:really|actually)|\s+(?:was|is|had been)"
                            r"(?:\s+(?:really|actually|in fact))?|\s+turned\s+out\s+to\s+be)\s+$", re.I)
# Resolved references that may stand for a person in a reveal; "this" or "it" may point at anything.
PERSONAL = {"i", "he", "she", "me", "him", "her"}
SAME_AFTER = re.compile(r"^\s+(?:were|are)\s+the\s+same\s+(?:person|man|woman|figure)\b", re.I)

Span = tuple[int, int]
Recognize = Callable[[list[str]], list[list[tuple[int, int, str]]]]
Corefer = Callable[[str], list[list[Span]]]


def normalize(surface: str) -> str:
    words = re.sub(r"[’']s\b", "", surface).replace("’", "'").split()
    while words and words[0].casefold() in DETERMINERS:
        words = words[1:]
    return " ".join(words).casefold().strip(" ,.;:!?\"“”")


def head(words: list[str]) -> str:
    """Head noun of a common phrase: "house" in "house by the ash tree"."""
    return next((words[i - 1] for i, w in enumerate(words) if i and w in PREPOSITIONS), words[-1])


def fold_names(names: set[str]) -> Callable[[str], str]:
    """A full name folds into a surname used alone; a lone first name into the one full name it starts."""
    surname = {n: n.split()[-1] for n in names if len(n.split()) > 1 and n.split()[-1] in names}
    firsts = defaultdict(set)
    for name in names:
        if len(name.split()) > 1:
            firsts[name.split()[0]].add(surname.get(name, name))

    def fold(name: str) -> str:
        name = surname.get(name, name)
        return next(iter(firsts[name])) if len(firsts.get(name, ())) == 1 and name not in surname.values() else name
    return fold


def extract(sources: list[dict], known: list[dict], recognize: Recognize, corefer: Corefer) -> dict:
    texts = [s["text"] for s in sources]
    raw = []  # (source index, start, end, label, surface, key)
    for index, spans in enumerate(recognize(texts)):
        for start, end, label in spans:
            surface = texts[index][start:end]
            key = normalize(surface)
            if key and key not in STOP and label in LABELS:
                raw.append((index, start, end, label, surface, key))

    # Identity: a proper name is one identity whatever its label; common nouns key on the head noun.
    known_names = {normalize(k["label"]): k for k in known if k["label"][:1].isupper()}
    proper_keys = set(known_names)
    for _, _, _, _, surface, key in raw:
        stripped = " ".join(w for w in key.split() if w not in TITLES)
        if stripped and surface.lstrip("“\"'(")[:1].isupper():
            proper_keys.add(stripped)
    fold = fold_names(proper_keys)
    identity_of, titled, title_owners = {}, [], defaultdict(set)
    for mention in raw:
        index, start, end, label, surface, key = mention
        words = key.split()
        stripped = " ".join(w for w in words if w not in TITLES)
        if not stripped:
            titled.append((mention, words[-1]))  # "the captain" stays ambiguous
        elif stripped in proper_keys:
            identity_of[mention] = ("name", fold(stripped))
            if words[0] in TITLES:
                title_owners[words[0]].add(("name", fold(stripped)))
        else:
            identity_of[mention] = ("common", head(words))

    # Keys: reuse an earlier chapter's entity when its folded label matches, otherwise declare one.
    earlier = {}
    for entry in known:
        name = normalize(entry["label"])
        if name:
            earlier.setdefault(("name", fold(name)) if name in known_names else ("common", head(name.split())),
                               entry["key"])
    labels, kinds = defaultdict(Counter), defaultdict(Counter)
    for mention, identity in identity_of.items():
        labels[identity][mention[4].strip()] += 1
        kinds[identity]["character" if identity[0] == "name" and mention[3] == "object" else mention[3]] += 1
    key_of, entities = {}, []
    for identity in dict.fromkeys(identity_of.values()):
        if identity in earlier:
            key_of[identity] = earlier[identity]
        else:
            key_of[identity] = f"e{len(entities)}"
            preferred = [s for s in labels[identity] if normalize(s) == identity[1]] or list(labels[identity])
            entities.append({"key": key_of[identity], "kind": kinds[identity].most_common(1)[0][0],
                             "label": max(preferred, key=lambda s: (labels[identity][s], len(s)))})

    mentions, located = [], {}
    for mention, identity in identity_of.items():
        index, start, end, _, surface, _ = mention
        located[(index, start, end)] = identity
        mentions.append({"ref": sources[index]["ref"], "quote": surface, "start": start, "entity": key_of[identity]})
    for (index, start, end, _, surface, _), title in titled:
        owners = sorted(key_of[o] for o in title_owners.get(title, ()) if o in key_of)
        if owners:
            mentions.append({"ref": sources[index]["ref"], "quote": surface, "start": start, "entity": None,
                             "candidates": owners[:8]})

    # Coreference over the batch; a cluster resolves its other mentions only when it holds exactly one identity.
    offsets, cursor = [], 0
    for text in texts:
        offsets.append(cursor)
        cursor += len(text) + 2
    joined = "\n\n".join(texts)

    def local(span):
        for index in range(len(texts) - 1, -1, -1):
            if span[0] >= offsets[index]:
                start, end = span[0] - offsets[index], span[1] - offsets[index]
                return (index, start, end) if end <= len(texts[index]) else None
        return None
    resolved = dict(located)
    for cluster in corefer(joined) if joined.strip() else []:
        spans = [s for s in (local(tuple(span)) for span in cluster) if s]
        identities = {located[s] for s in spans if s in located}
        if len(identities) != 1:
            continue
        identity = identities.pop()
        for span in spans:
            if span not in located:
                resolved[span] = identity
                index, start, end = span
                mentions.append({"ref": sources[index]["ref"], "quote": texts[index][start:end], "start": start,
                                 "entity": key_of[identity]})

    # Explicit reveals between two named identities: "I was Wren", "Wren and Arthur were the same person".
    relations, aliases, by_source = [], [], defaultdict(list)
    for (index, start, end), identity in resolved.items():
        named = (index, start, end) in located or texts[index][start:end].casefold() in PERSONAL
        if identity[0] == "name" and named:
            by_source[index].append((start, end, identity))
    count = Counter(resolved.values())  # the alias goes on the identity the text mentions most
    for index, spans in by_source.items():
        text = texts[index]
        spans.sort()
        for (a_start, a_end, a), (b_start, b_end, b) in zip(spans, spans[1:]):
            if a == b or re.match(r"[’']s\b", text[b_end:b_end + 2]):
                continue
            between, tail = text[a_end:b_start], SAME_AFTER.match(text[b_end:])
            if REVEAL_BETWEEN.match(between) or (between.strip().casefold() == "and" and tail):
                end = b_end + (tail.end() if tail and between.strip().casefold() == "and" else 0)
                quote = text[a_start:end]
                relations.append({"subject": key_of[a], "relation": "same_as", "object": key_of[b],
                                  "ref": sources[index]["ref"], "quote": quote, "start": a_start})
                main, other = sorted((a, b), key=lambda i: -count[i])
                label = next((e["label"] for e in [*entities, *known] if e["key"] == key_of[other]), None)
                if label and label.casefold() in quote.casefold():
                    aliases.append({"entity": key_of[main], "label": label, "status": "supported",
                                    "ref": sources[index]["ref"], "quote": quote, "start": a_start})
    return {"entities": entities, "mentions": mentions[:1_000], "aliases": aliases[:200], "relations": relations[:200]}


@cache
def snapshot(repo: str, revision: str) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(repo, revision=revision)


@cache
def models():
    from fastcoref import FCoref
    from gliner2 import GLiNER2
    return GLiNER2.from_pretrained(snapshot(*GLINER)), FCoref(model_name_or_path=snapshot(*COREF), device="cpu",
                                                              enable_progress_bar=False)


def gliner_recognize(texts):
    # One passage per forward pass: on Jekyll's longest passages batch 8 added 2.3 GB of padded attention at peak
    # and ran slower, with byte-identical spans (T44).
    found = models()[0].batch_extract_entities(texts, LABELS, batch_size=1, threshold=0.5, include_spans=True)
    spans = []
    for result in found:
        items = result.get("entities", result)
        spans.append([(i["start"], i["end"], label) for label, values in items.items()
                      for i in values if isinstance(i, dict) and "start" in i])
    return spans


def fastcoref_corefer(text):
    return [[tuple(span) for span in cluster]
            for cluster in models()[1].predict(texts=[text])[0].get_clusters(as_strings=False)]


class LocalEntities:
    """Entity extraction with pinned local models; recognisers are injectable for tests."""

    provider = "local"
    model = f"gliner2-{GLINER[1][:8]}+fcoref-{COREF[1][:8]}+{RULES_VERSION}"

    def __init__(self, recognize: Recognize = gliner_recognize, corefer: Corefer = fastcoref_corefer):
        self.recognize, self.corefer = recognize, corefer

    def complete(self, call: ProviderCall) -> ProviderResult:
        items = json.loads(call.data)["sources"]
        sources = [i for i in items if i["ref"] != KNOWN_REF]
        known = next((json.loads(i["text"]) for i in items if i["ref"] == KNOWN_REF), [])
        output = json.dumps(extract(sources, known, self.recognize, self.corefer), ensure_ascii=False)
        return ProviderResult(output=output, usage=Usage(input_tokens=0, output_tokens=0), model_version=RULES_VERSION)
