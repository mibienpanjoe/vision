"""Local-first processing spike: measure on-device NLP components against the annotated corpus.

Runs one component per invocation so wall time and peak memory are attributable:

    python local_pipeline.py entities  --corpus synthetic|jekyll [--int8]
    python local_pipeline.py appearance --corpus synthetic|jekyll [--int8]
    python local_pipeline.py retrieval --corpus synthetic [--int8]
    python local_pipeline.py novel_retrieval [--int8] [--gemma-direct]
    python local_pipeline.py grounding [--int8]
    python local_pipeline.py generator --model qwen3:4b

Requires the separate spike environment (see docs/research/local-first-processing.md);
it never touches the application database or sends text off the machine except to
the local Ollama server.
"""

import argparse
import json
import math
import re
import resource
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "apps/api/tests/fixtures/narrative/expected.json"
JEKYLL = ROOT / ".local/spike/corpus/jekyll.txt"
RESULTS = ROOT / ".local/spike/results"
OLLAMA = "http://127.0.0.1:11434"

LABELS = {"character": "a person or creature in the story, named or described",
          "place": "a location, building, room or landscape",
          "object": "a physical object, item, garment or weapon",
          "organization": "a group, institution or company"}
TITLES = {"captain", "mr", "mr.", "mrs", "mrs.", "dr", "dr.", "miss", "sir", "lady", "lord", "master"}
DETERMINERS = {"the", "a", "an", "his", "her", "their", "its", "my", "our", "your"}
PREPOSITIONS = {"by", "of", "with", "in", "on", "at", "near", "from", "under"}
PRONOUNS = {"he", "him", "his", "she", "her", "hers", "they", "them", "their", "it", "its", "i", "me", "my"}
# Surface forms identifying annotated entities; mirrors apps/api/tests/narrative_eval.py.
SURFACES = {"arthur": {"arthur"}, "elodie": {"élodie"}, "mira": {"mira", "captain mira"},
            "brann": {"brann", "captain brann"}, "wren": {"wren", "masked visitor", "visitor"},
            "house": {"house", "house by the ash tree"}, "compass": {"compass", "brass compass"},
            "sword": {"sword", "silver sword"}}
APPEARANCE_WORDS = re.compile(
    r"\b(hair|eyes?|cheek|face|scar|skin|wore|wearing|dressed|coat|armou?r|shirt|cloak|mask|roof|slate|"
    r"sword|compass|brass|silver|candlelight|light|tall|short|pale|dark|stooped|dwarfish|deformed|"
    r"hand|hands|smile|clothes|clothing|figure|stature|built|lean|ugly|handsome)\b", re.I)


# ----------------------------------------------------------------- corpora

def synthetic():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    passages = [(p["id"], p["chapter"], p["text"]) for p in data["passages"]]
    return passages, data


def jekyll():
    raw = JEKYLL.read_text(encoding="utf-8")
    body = raw.split("*** START OF THE PROJECT GUTENBERG EBOOK", 1)[1].split("***", 1)[1]
    body = body.split("*** END OF THE PROJECT GUTENBERG EBOOK", 1)[0]
    headings = ["STORY OF THE DOOR", "SEARCH FOR MR. HYDE", "DR. JEKYLL WAS QUITE AT EASE", "THE CAREW MURDER CASE",
                "INCIDENT OF THE LETTER", "INCIDENT OF DR. LANYON", "INCIDENT AT THE WINDOW", "THE LAST NIGHT",
                "DR. LANYON’S NARRATIVE", "HENRY JEKYLL’S FULL STATEMENT OF THE CASE"]
    passages, chapter = [], 0
    for block in re.split(r"\n\s*\n", body):
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text in headings:
            chapter = headings.index(text) + 1
            continue
        if chapter and len(text) > 20:
            passages.append((f"j{len(passages):04d}", chapter, text))
    return passages, None


def corpus(name):
    return synthetic() if name == "synthetic" else jekyll()


def sentences(text):
    return [(m.start(), m.end()) for m in re.finditer(r"[^.!?]+[.!?]+[\"”’]?|[^.!?]+$", text) if m.group().strip()]


# ----------------------------------------------------------------- helpers

def peak_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)


def quantize(module):
    """Dynamic int8 for Linear layers, skipping torch TransformerEncoderLayer, whose fast path needs float weights."""
    import torch
    skip = {name for name, sub in module.named_modules() if isinstance(sub, torch.nn.TransformerEncoderLayer)}
    targets = {name for name, sub in module.named_modules() if isinstance(sub, torch.nn.Linear)
               and not any(name == s or name.startswith(s + ".") for s in skip)}
    return torch.ao.quantization.quantize_dynamic(module, targets, dtype=torch.qint8)


def save(name, result):
    RESULTS.mkdir(parents=True, exist_ok=True)
    result["peak_rss_mb"] = peak_mb()
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(json.dumps(result, ensure_ascii=False, indent=1)[:4000])


def normalize(surface):
    words = [w for w in re.sub(r"[’']s\b", "", surface).replace("’", "'").split()]
    while words and words[0].casefold() in DETERMINERS:
        words = words[1:]
    return " ".join(words).casefold().strip(" ,.;:!?\"“”")


# ----------------------------------------------------------------- entities

def entities(args):
    from gliner2 import GLiNER2
    passages, data = corpus(args.corpus)
    started = time.monotonic()
    model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
    if args.int8:  # the DeBERTa backbone holds about 90% of the weights; span heads read raw weights
        model.encoder = quantize(model.encoder)
    loaded = time.monotonic()
    raw = model.batch_extract_entities([t for _, _, t in passages], LABELS, batch_size=8, threshold=0.5,
                                       include_spans=True, include_confidence=True)
    ner_seconds = time.monotonic() - loaded
    mentions = []  # (passage index, start, end, label, surface)
    for index, result in enumerate(raw):
        found = result.get("entities", result)
        for label, items in found.items():
            for item in items:
                if isinstance(item, dict) and "start" in item:
                    mentions.append((index, item["start"], item["end"], label, passages[index][2][item["start"]:item["end"]]))

    # Identity: proper names create entities; a title alone stays ambiguous; common nouns key on the head word.
    entity_of, ambiguous = {}, []
    names = {normalize(s) for _, _, _, label, s in mentions if s[:1].isupper() and normalize(s).split()
             and normalize(s).split()[0] not in TITLES}
    for m in mentions:
        key = normalize(m[4])
        words = key.split()
        if not words or key in PRONOUNS:
            continue
        stripped = " ".join(w for w in words if w not in TITLES)
        if not stripped:
            ambiguous.append(m)
            continue
        if stripped in names:
            entity_of[m] = (m[3] if m[3] != "object" else "character", stripped)
        elif m[4][:1].isupper():
            entity_of[m] = (m[3], stripped)
        else:
            head = next((words[i - 1] for i, w in enumerate(words) if i and w in PREPOSITIONS), words[-1])
            entity_of[m] = ("common", head)  # head noun ("house" in "house by the ash tree"), whatever the label
    coref_seconds, coref_links = 0.0, 0
    if args.coref:
        from fastcoref import FCoref
        coref = FCoref(device="cpu")
        if args.int8:
            coref.model = quantize(coref.model)
        chapters = defaultdict(list)
        for index, (_, chapter, text) in enumerate(passages):
            chapters[chapter].append(index)
        coref_started = time.monotonic()
        for chapter, indexes in chapters.items():
            offsets, parts, cursor = {}, [], 0
            for index in indexes:
                offsets[index] = cursor
                parts.append(passages[index][2])
                cursor += len(passages[index][2]) + 2
            text = "\n\n".join(parts)
            clusters = coref.predict(texts=[text])[0].get_clusters(as_strings=False)
            located = {(offsets[m[0]] + m[1], offsets[m[0]] + m[2]): entity_of[m] for m in entity_of if m[0] in offsets}
            for cluster in clusters:
                linked = Counter(located[tuple(span)] for span in cluster if tuple(span) in located)
                if len(linked) == 1:
                    coref_links += sum(1 for span in cluster if tuple(span) not in located)
        coref_seconds = time.monotonic() - coref_started
    clusters = defaultdict(set)
    for m, identity in entity_of.items():
        clusters[identity].add(normalize(m[4]))
    result = {"component": "entities", "corpus": args.corpus, "int8": args.int8, "coref": args.coref,
              "passages": len(passages), "characters": sum(len(t) for _, _, t in passages),
              "load_s": round(loaded - started, 1), "ner_s": round(ner_seconds, 1), "coref_s": round(coref_seconds, 1),
              "mentions": len(mentions), "entities": len(clusters), "ambiguous_titles": len(ambiguous),
              "pronoun_links_from_coref": coref_links,
              "top_entities": sorted(((f"{k[0]}:{k[1]}", len([m for m in entity_of if entity_of[m] == k]))
                                      for k in clusters), key=lambda x: -x[1])[:25]}
    if data is not None:
        matched = defaultdict(set)
        for m, identity in entity_of.items():
            for expected, forms in SURFACES.items():
                if normalize(m[4]) in forms:
                    matched[identity].add(expected)
        by_expected = defaultdict(set)
        for identity, names_ in matched.items():
            for name in names_:
                by_expected[name].add(identity)
        result["evaluation"] = {
            "misses": sorted(set(SURFACES) - set(by_expected)),
            "false_merges": sorted(sorted(v) for v in matched.values() if len(v) > 1),
            "splits": sorted(n for n, ids in by_expected.items() if len(ids) > 1),
            "captain_resolved_to_one": [m[4] for m in entity_of if normalize(m[4]) == "captain"],
            "ambiguous_titles": [m[4] for m in ambiguous],
        }
    save(f"entities-{args.corpus}-{'int8' if args.int8 else 'fp32'}{'-coref' if args.coref else ''}", result)


# ----------------------------------------------------------------- appearance passages

def appearance(args):
    from gliner2 import GLiNER2
    passages, data = corpus(args.corpus)
    units = [(pid, text[s:e].strip()) for pid, _, text in passages for s, e in sentences(text)]
    model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
    if args.int8:  # the DeBERTa backbone holds about 90% of the weights; span heads read raw weights
        model.encoder = quantize(model.encoder)
    started = time.monotonic()
    tasks = {"description": ["physical appearance, clothing, object or setting description", "other"]}
    raw = model.batch_classify_text([u for _, u in units], tasks, batch_size=8)
    seconds = time.monotonic() - started
    predicted = [str(r.get("description", r)).startswith("physical") for r in raw]
    patterned = [bool(APPEARANCE_WORDS.search(u)) for _, u in units]
    result = {"component": "appearance", "corpus": args.corpus, "int8": args.int8, "sentences": len(units),
              "classify_s": round(seconds, 1), "classifier_positive": sum(predicted), "pattern_positive": sum(patterned)}
    if data is not None:
        spans = {s["id"]: s for s in data["spans"]}
        quotes = {spans[e]["quote"] for f in data["facts"] for e in f["evidence"]}
        gold = [any(q in u or u in q for q in quotes) for _, u in units]

        def score(pred):
            tp = sum(p and g for p, g in zip(pred, gold))
            return {"precision": round(tp / max(1, sum(pred)), 2), "recall": round(tp / max(1, sum(gold)), 2)}
        result.update(gold_positive=sum(gold), classifier=score(predicted), pattern=score(patterned),
                      union=score([a or b for a, b in zip(predicted, patterned)]))
    else:
        result["examples"] = [u[:160] for (_, u), p in zip(units, predicted) if p][:12]
    save(f"appearance-{args.corpus}-{'int8' if args.int8 else 'fp32'}", result)


# ----------------------------------------------------------------- retrieval

QUERY_SUBJECT = {"arthur": "Arthur", "house": "the house by the ash tree", "mira": "Mira",
                 "compass": "the brass compass", "sword": "the silver sword"}
QUERY_EVENT = {"child": "as a child at age ten before the war", "war": "during the war and the battle",
               "journey": "travelling home after the war", "dinner": "at dinner at home after the war",
               "spring": "the following spring after the return"}


def bm25(docs, query, k1=1.5, b=0.75):
    tokens = [re.findall(r"\w+", d.casefold()) for d in docs]
    avg = sum(map(len, tokens)) / len(tokens)
    df = Counter(t for doc in tokens for t in set(doc))
    q = re.findall(r"\w+", query.casefold())
    scores = []
    for doc in tokens:
        tf = Counter(doc)
        scores.append(sum(math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * (k1 + 1)
                          / (tf[t] + k1 * (1 - b + b * len(doc) / avg)) for t in q if t in tf))
    return scores


def ollama_embed(model, texts):
    body = json.dumps({"model": model, "input": texts}).encode()
    request = urllib.request.Request(f"{OLLAMA}/api/embed", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())["embeddings"]


def retrieval(args):
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer
    passages, data = synthetic()
    spans = {s["id"]: s for s in data["spans"]}
    facts = {f["id"]: f for f in data["facts"]}
    texts = [t for _, _, t in passages]
    chapter = [c for _, c, _ in passages]
    pid = [p for p, _, _ in passages]
    encoders = {}
    started = time.monotonic()
    bge = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    if args.int8:
        bge = quantize(bge)
    doc_vectors = {"bge-small": bge.encode(texts, normalize_embeddings=True)}
    encoders["bge-small"] = lambda q: bge.encode(["Represent this sentence for searching relevant passages: " + q],
                                                 normalize_embeddings=True)[0]
    try:
        doc_vectors["embeddinggemma"] = np.array(ollama_embed("embeddinggemma", [f"title: none | text: {t}" for t in texts]))
        doc_vectors["embeddinggemma"] /= np.linalg.norm(doc_vectors["embeddinggemma"], axis=1, keepdims=True)
        encoders["embeddinggemma"] = lambda q: (lambda v: v / np.linalg.norm(v))(
            np.array(ollama_embed("embeddinggemma", [f"task: search result | query: {q}"])[0]))
    except Exception as error:
        print("embeddinggemma unavailable:", type(error).__name__)
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", device="cpu")
    if args.int8:
        reranker.model = quantize(reranker.model)
    index_seconds = time.monotonic() - started

    def recall(ranked, gold, k):
        return len(set(ranked[:k]) & gold) / len(gold)

    rows = defaultdict(lambda: defaultdict(list))
    for case in data["cases"]:
        needed = case["canonical"] + case["inferred"] + case["disputed"]
        if not needed or case["subject"] not in QUERY_SUBJECT:
            continue
        gold = {spans[e]["passage_id"] for f in needed for e in facts[f]["evidence"]
                if next(c for p, c, _ in passages if p == spans[e]["passage_id"]) <= case["through_chapter"]}
        allowed = [i for i in range(len(texts)) if chapter[i] <= case["through_chapter"]]  # cutoff before retrieval
        query = f"{QUERY_SUBJECT[case['subject']]} appearance {QUERY_EVENT[case['event']]}"
        lexical = bm25([texts[i] for i in allowed], query)
        rankings = {"bm25": [pid[allowed[j]] for j in np.argsort(lexical)[::-1]]}
        for name, vectors in doc_vectors.items():
            scores = vectors[allowed] @ encoders[name](query)
            rankings[name] = [pid[allowed[j]] for j in np.argsort(scores)[::-1]]
        fused = Counter()
        for name in rankings:
            for rank, p in enumerate(rankings[name]):
                fused[p] += 1 / (60 + rank)
        rankings["rrf"] = [p for p, _ in fused.most_common()]
        top = rankings["rrf"][:10]
        scores = reranker.predict([(query, texts[pid.index(p)]) for p in top])
        rankings["rrf+rerank"] = [top[j] for j in np.argsort(scores)[::-1]] + rankings["rrf"][10:]
        for name, ranked in rankings.items():
            for k in (3, 5):
                rows[name][f"recall@{k}"].append(recall(ranked, gold, k))
    result = {"component": "retrieval", "int8": args.int8, "cases": len(rows["bm25"]["recall@3"]),
              "index_s": round(index_seconds, 1),
              "methods": {name: {k: round(sum(v) / len(v), 2) for k, v in metrics.items()} for name, metrics in rows.items()}}
    save(f"retrieval-synthetic-{'int8' if args.int8 else 'fp32'}", result)


NOVEL_QUERIES = {  # query -> distinctive phrases that identify the gold passages in the public-domain text
    "What does Mr Hyde look like?": ["dwarfish", "deformity", "deformed"],
    "Utterson the lawyer's face and appearance": ["rugged countenance"],
    "Dr Jekyll's hand compared with Hyde's hand": ["corded, knuckly", "comely"],
    "the door and the building in the by-street": ["blistered and distained", "sinister block of building"],
}


def novel_retrieval(args):
    import numpy as np
    from sentence_transformers import SentenceTransformer
    passages, _ = jekyll()
    texts = [t for _, _, t in passages]
    timings, vectors, encoders = {}, {}, {}
    started = time.monotonic()
    bge = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    if args.int8:
        bge = quantize(bge)
    vectors["bge-small"] = bge.encode(texts, normalize_embeddings=True, batch_size=16)
    timings["bge-small_index_s"] = round(time.monotonic() - started, 1)
    encoders["bge-small"] = lambda q: bge.encode(["Represent this sentence for searching relevant passages: " + q],
                                                 normalize_embeddings=True)[0]
    started = time.monotonic()
    if args.gemma_direct:  # official Hugging Face weights; needs the licence and HF_TOKEN
        model = SentenceTransformer("google/embeddinggemma-300m", device="cpu")
        vectors["embeddinggemma"] = model.encode_document(texts, normalize_embeddings=True, batch_size=16)
        encoders["embeddinggemma"] = lambda q: model.encode_query([q], normalize_embeddings=True)[0]
    else:
        gemma = np.array([v for i in range(0, len(texts), 32)
                          for v in ollama_embed("embeddinggemma", [f"title: none | text: {t}" for t in texts[i:i + 32]])])
        vectors["embeddinggemma"] = gemma / np.linalg.norm(gemma, axis=1, keepdims=True)
        encoders["embeddinggemma"] = lambda q: (lambda v: v / np.linalg.norm(v))(
            np.array(ollama_embed("embeddinggemma", [f"task: search result | query: {q}"])[0]))
    timings["embeddinggemma_index_s"] = round(time.monotonic() - started, 1)
    rows = defaultdict(list)
    for query, phrases in NOVEL_QUERIES.items():
        gold = {i for i, t in enumerate(texts) if any(p in t for p in phrases)}
        rankings = {"bm25": list(np.argsort(bm25(texts, query))[::-1])}
        for name in vectors:
            rankings[name] = list(np.argsort(vectors[name] @ encoders[name](query))[::-1])
        fused = Counter()
        for ranked in rankings.values():
            for rank, i in enumerate(ranked):
                fused[i] += 1 / (60 + rank)
        rankings["rrf"] = [i for i, _ in fused.most_common()]
        for name, ranked in rankings.items():
            rows[name].append(len(set(ranked[:5]) & gold) / len(gold))
    save(f"retrieval-jekyll-{'int8' if args.int8 else 'fp32'}{'-gemma-direct' if args.gemma_direct else ''}",
         {"component": "novel_retrieval", "int8": args.int8, "gemma_direct": args.gemma_direct,
          "passages": len(texts), **timings,
          "recall@5": {name: round(sum(v) / len(v), 2) for name, v in rows.items()},
          "per_query": {name: [round(x, 2) for x in v] for name, v in rows.items()}})


# ----------------------------------------------------------------- grounding check

CLAIMS = [  # premise (source span), hypothesis, should the source support it?
    ("At ten, Arthur had chestnut hair and an unmarked left cheek.", "Arthur had chestnut hair as a child.", True),
    ("Ten years later, during the war, a blade cut Arthur's left cheek and left a scar.", "Arthur has a scar on his left cheek.", True),
    ("Arthur wore steel armor.", "Arthur wore steel armor.", True),
    ("Before dinner, Arthur removed his steel armor and put on a plain linen shirt.", "At dinner Arthur wore a plain linen shirt.", True),
    ("At dinner his left-cheek scar was still visible.", "Arthur's scar was visible at dinner.", True),
    ("The house had an intact slate roof.", "The house had an intact slate roof.", True),
    ("Captain Mira carried a brass compass.", "Mira carried a brass compass.", True),
    ("Brann, not Arthur, held the silver sword.", "Brann held the silver sword.", True),
    ("By the following spring, builders had restored the slate roof.", "The roof was restored by spring.", True),
    ("Brann, not Arthur, held the silver sword.", "Arthur held the silver sword.", False),
    ('"Are you wearing armor?" Élodie asked Arthur. "No, I removed it before dinner," he replied.',
     "Arthur was wearing armor at dinner.", False),
    ("People claim Arthur has golden eyes, but I have never seen them.", "Arthur has golden eyes.", False),
    ("A poet called Arthur a wolf made of iron.", "Arthur's body is made of iron.", False),
    ("That night Arthur dreamed that he had wings.", "Arthur had wings.", False),
    ("the other said his eyes were blue.", "Arthur's eyes were green.", False),
    ("During the same battle, fire destroyed the house's slate roof.", "The house had an intact roof during the battle.", False),
    ("Neither described his adult hair color.", "Arthur had chestnut hair as an adult.", False),
    ("Captain Mira carried a brass compass.", "Mira carried a silver sword.", False),
]


def grounding(args):
    from transformers import AutoModelForSequenceClassification
    started = time.monotonic()
    model = AutoModelForSequenceClassification.from_pretrained("vectara/hallucination_evaluation_model", trust_remote_code=True)
    if args.int8:
        model = quantize(model)
    loaded = time.monotonic()
    scores = model.predict([(p, h) for p, h, _ in CLAIMS]).tolist()
    seconds = time.monotonic() - loaded
    correct = [(s >= 0.5) == expected for s, (_, _, expected) in zip(scores, CLAIMS)]
    result = {"component": "grounding", "int8": args.int8, "pairs": len(CLAIMS), "load_s": round(loaded - started, 1),
              "score_s": round(seconds, 2), "accuracy": round(sum(correct) / len(correct), 2),
              "supported_accepted": sum(c for c, (_, _, e) in zip(correct, CLAIMS) if e),
              "unsupported_rejected": sum(c for c, (_, _, e) in zip(correct, CLAIMS) if not e),
              "errors": [{"hypothesis": h, "score": round(s, 3), "expected": e}
                         for s, (_, h, e), ok in zip(scores, CLAIMS, correct) if not ok]}
    save(f"grounding-{'int8' if args.int8 else 'fp32'}", result)


# ----------------------------------------------------------------- local generator

def generator(args):
    passages, data = synthetic()
    by_id = {p: t for p, _, t in passages}
    schema = {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {"facts": {
        "type": "array", "items": {"type": "object", "additionalProperties": False,
                                   "required": ["attribute", "value", "quote", "modality"],
                                   "properties": {"attribute": {"type": "string"}, "value": {"type": "string"},
                                                  "quote": {"type": "string"},
                                                  "modality": {"enum": ["fact", "memory", "dream", "rumor", "metaphor"]}}}}}}
    cases = [("Arthur at dinner at home after the war", ["p08", "p09", "p11"]),
             ("Arthur during the war", ["p04", "p05"]),
             ("the house by the ash tree when they returned home", ["p06", "p10"])]
    rows = []
    for question, refs in cases:
        evidence = "\n".join(f"[{r}] {by_id[r]}" for r in refs)
        prompt = (f"List visual facts about {question} stated in the passages. Copy each quote exactly. "
                  f"Mark dreams, rumors and metaphors with their modality.\n\n{evidence}")
        body = json.dumps({"model": args.model, "prompt": prompt, "format": schema, "stream": False, "think": False,
                           "options": {"temperature": 0, "num_predict": 800}}).encode()
        started = time.monotonic()
        request = urllib.request.Request(f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=1200) as response:
            reply = json.loads(response.read())
        seconds = time.monotonic() - started
        try:
            facts = json.loads(reply["response"])["facts"]
        except (ValueError, KeyError, TypeError):
            facts = None
        grounded = [f for f in facts or [] if any(f["quote"] in by_id[r] for r in refs)]
        rows.append({"question": question, "seconds": round(seconds, 1), "valid_json": facts is not None,
                     "facts": len(facts or []), "grounded_quotes": len(grounded),
                     "tokens_per_s": round(reply.get("eval_count", 0) / max(1e-9, reply.get("eval_duration", 1) / 1e9), 1),
                     "output": facts})
    save(f"generator-{args.model.replace(':', '-')}", {"component": "generator", "model": args.model, "cases": rows})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("component", choices=["entities", "appearance", "retrieval", "novel_retrieval", "grounding", "generator"])
    parser.add_argument("--corpus", choices=["synthetic", "jekyll"], default="synthetic")
    parser.add_argument("--int8", action="store_true")
    parser.add_argument("--coref", action="store_true")
    parser.add_argument("--gemma-direct", action="store_true")
    parser.add_argument("--model", default="qwen3:4b")
    args = parser.parse_args()
    globals()[args.component](args)


if __name__ == "__main__":
    sys.exit(main())
