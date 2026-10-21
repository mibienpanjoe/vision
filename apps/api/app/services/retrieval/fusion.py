"""Weighted reciprocal-rank fusion and a budgeted, protection-preserving selection.

Fusion orders passages; it decides nothing about which visual facts are true.
Each candidate keeps the paths that found it. Protected description sentences
are reserved before any ranked passage, so a low similarity score never drops
them; a protected passage is sent whole only when its rank earns a slot. If the
protected sentences alone exceed the budget the selection says so instead of
dropping them silently.
"""

import re
import uuid
from dataclasses import dataclass, field

from app.services.narrative.appearance import CUES
from app.services.retrieval.evidence import Candidate

K = 60
# ADR-0003: EmbeddingGemma ranks first; weights measured on Jekyll (DEC-42). Entity and appearance paths still
# supply anchors and protection; giving them rank weight lowered recall@5 without raising selection recall.
WEIGHTS = {"semantic": 1.0, "lexical": 0.5, "entity": 0.0, "appearance": 0.0}
DIVERSITY_WINDOW = 40
CATEGORIES = {
    "body": "hair eyes eye face cheek cheeks skin scar scars beard moustache brow lips mouth hand hands figure stature "
            "height tall short pale dark fair stooped lean thin stout ugly handsome beautiful deformed dwarfish",
    "attire": "wore wearing worn dressed coat cloak armor armour shirt dress gown hat boots mask clothes clothing uniform",
    "colour_material": "red blue green black white grey gray golden silver brass brown chestnut steel iron wooden stone "
                       "slate brick",
    "structure": "roof wall walls window windows",
    "light": "candlelight lamplight fog",
}
CATEGORY = {word: name for name, words in CATEGORIES.items() for word in words.split()}


@dataclass(frozen=True)
class PassageInfo:
    ordinal: int
    text: str


@dataclass
class Ranked:
    passage_id: uuid.UUID
    score: float
    paths: dict[str, int]
    protected: list[tuple[int, int]] = field(default_factory=list)
    anchors: set[tuple[int, int]] = field(default_factory=set)


@dataclass(frozen=True)
class Budget:
    passages: int = 20
    characters: int = 20_000  # about 5,000 tokens (ADR-0003 target)


@dataclass
class Selected:
    passage_id: uuid.UUID
    spans: list[tuple[int, int]]  # the whole passage, or only its protected sentences when compressed
    paths: dict[str, int]
    protected: list[tuple[int, int]]
    compressed: bool


@dataclass
class Selection:
    passages: list[Selected]
    # complete: every candidate is sent whole; compressed: some protected passages are sent as their protected
    # sentences only; truncated: lower-ranked unprotected passages are left out;
    # protected_overflow: protected sentences alone exceed the budget and some are missing.
    outcome: str
    omitted: int
    protected_omitted: int
    categories: list[str]


def categories(text: str) -> set[str]:
    return {CATEGORY[w.casefold()] for w in CUES.findall(text) if w.casefold() in CATEGORY}


def fuse(candidates: list[Candidate], weights: dict[str, float] = WEIGHTS, k: int = K) -> list[Ranked]:
    """Passages by weighted RRF over their best rank per path; protected spans and anchors carried along."""
    by_passage: dict[uuid.UUID, Ranked] = {}
    for item in candidates:
        ranked = by_passage.setdefault(item.passage_id, Ranked(item.passage_id, 0.0, {}))
        for path, rank in item.paths.items():
            ranked.paths[path] = min(rank, ranked.paths.get(path, rank))
        if item.protected:
            ranked.protected.append((item.start, item.end))
        ranked.anchors |= item.anchors
    for ranked in by_passage.values():
        ranked.score = sum(weights.get(path, 0.0) / (k + rank) for path, rank in ranked.paths.items())
        ranked.protected.sort()
    return sorted(by_passage.values(), key=lambda r: (-r.score, str(r.passage_id)))


def fingerprint(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def select(ranked: list[Ranked], passages: dict[uuid.UUID, PassageInfo], budget: Budget = Budget()) -> Selection:
    """Reserve protected sentences, then whole passages: first one per uncovered visual category near the top,
    then by rank. Near-duplicate passages are sent once. Measured on Jekyll: selection recall 0.93 against 0.79
    for taking whole protected passages first (DEC-42)."""
    chosen: dict[uuid.UUID, Selected] = {}
    used, whole, seen, covered = 0, 0, set(), set()
    protected_omitted = 0
    for item in (r for r in ranked if r.protected):
        size = sum(end - start for start, end in item.protected)
        if used + size > budget.characters:
            protected_omitted += len(item.protected)
            continue
        chosen[item.passage_id] = Selected(item.passage_id, list(item.protected), item.paths, item.protected, True)
        used += size
        text = passages[item.passage_id].text
        covered |= categories(" ".join(text[start:end] for start, end in item.protected))

    def take(item: Ranked) -> None:
        nonlocal used, whole
        text = passages[item.passage_id].text
        current = chosen.get(item.passage_id)
        if fingerprint(text) in seen or (current and not current.compressed):
            return
        extra = len(text) - (sum(end - start for start, end in current.spans) if current else 0)
        if whole >= budget.passages or used + extra > budget.characters:
            return
        chosen[item.passage_id] = Selected(item.passage_id, [(0, len(text))], item.paths, item.protected, False)
        used, whole = used + extra, whole + 1
        seen.add(fingerprint(text))
        covered.update(categories(text))

    for item in ranked[:DIVERSITY_WINDOW]:
        if categories(passages[item.passage_id].text) - covered:
            take(item)
    for item in ranked:
        take(item)

    duplicates = sum(1 for r in ranked if r.passage_id not in chosen and fingerprint(passages[r.passage_id].text) in seen)
    omitted = sum(1 for r in ranked if r.passage_id not in chosen) - duplicates
    compressed = any(s.compressed for s in chosen.values())
    outcome = ("protected_overflow" if protected_omitted else "truncated" if omitted
               else "compressed" if compressed else "complete")
    order = {r.passage_id: i for i, r in enumerate(ranked)}
    return Selection(sorted(chosen.values(), key=lambda s: order[s.passage_id]), outcome, omitted, protected_omitted,
                     sorted(covered))
