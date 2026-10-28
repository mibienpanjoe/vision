"""Appearance of one subject at one story moment, computed from gated claims and partial chronology.

The conservative carry-forward rule (DEC-22, narrative contract "Appearance
claims"): a claim tied to the requested event applies directly and is canonical
when explicit; an earlier acquired change reaches a later moment only as a
labelled inference, and only the latest one by chronology; identity traits and
intervals tied to other events stay there ("not automatically valid at every
age"), and an untimed stable trait is an inference everywhere; scene clothing,
props and lighting never carry; an explicit removal blocks a value; a later or
unordered claim never applies. Two canonical claims that
disagree at the moment are disputed, never averaged. Kind labels from a model
are not trusted to widen applicability: an identity claim tied to one event is
still tied to it.
"""

import re
from collections.abc import Hashable
from dataclasses import dataclass, field

from app.services.narrative.chronology import Chronology

CANONICAL_MODALITY = frozenset({"fact", "memory"})
UNTIMED = frozenset({"identity", "acquired", "interval"})
CORE = {"character": ("hair", "eyes", "attire"), "place": (), "object": ("material",), "organization": ()}
SYNONYMS = [(re.compile(r"^(hair|hair_.*|.*_hair)$"), "hair"), (re.compile(r"^(eyes?|eye_.*|.*_eyes?)$"), "eyes"),
            (re.compile(r"^(attire|cloth.*|clothes|outfit|garment.*|dress|coat|armou?r|shirt|wear.*|worn)(_.*)?$"),
             "attire"),
            (re.compile(r"^(material|.*_material)$"), "material")]


QUALIFIERS = frozenset("color colour material scar scars mark marked marking decoration style length shape type state "
                       "condition exclusion pattern".split())


def part(attribute: str) -> str:
    """The body part or item a trait describes ("left_cheek_scar" -> "left_cheek"), for supersession."""
    tokens = attribute.casefold().split("_")
    while len(tokens) > 1 and tokens[-1] in QUALIFIERS:
        tokens.pop()
    return "eyes" if tokens == ["eye"] else "_".join(tokens)


def attribute_key(attribute: str) -> str:
    """Group a model's attribute names ("hair_color", "eye_color") under the core trait they describe."""
    for pattern, key in SYNONYMS:
        if pattern.match(attribute):
            return key
    return attribute


@dataclass(frozen=True)
class Fact:
    id: Hashable
    subject: Hashable
    attribute: str
    value: str
    kind: str
    support: str  # explicit or inferred
    modality: str
    polarity: str
    events: frozenset
    assumption: str | None = None

    @property
    def explained(self) -> bool:
        return self.support != "inferred" or bool(self.assumption and self.assumption.strip())

    @property
    def canonical(self) -> bool:
        return self.support == "explicit" and self.polarity == "affirmed" and self.modality in CANONICAL_MODALITY


@dataclass
class Trait:
    attribute: str
    status: str  # canonical, inferred or disputed
    values: list[str]
    facts: list[Hashable]
    reason: str | None = None


@dataclass
class State:
    outcome: str  # resolved, needs_context or insufficient_evidence
    event: Hashable | None
    traits: dict[str, Trait] = field(default_factory=dict)
    excluded: dict[Hashable, str] = field(default_factory=dict)  # fact id -> reason
    unknown: list[str] = field(default_factory=list)
    choices: list[Hashable] = field(default_factory=list)  # events to choose from when the moment is unspecified


def same(a: str, b: str) -> bool:
    return a.casefold().strip() == b.casefold().strip()


def position(fact: Fact, event, chronology: Chronology) -> str:
    """direct, before, after or unordered relative to the requested event."""
    if event in fact.events or any(chronology.order(e, event) == "overlaps" for e in fact.events):
        return "direct"
    orders = {chronology.order(e, event) for e in fact.events}
    return orders.pop() if len(orders) == 1 and orders <= {"before", "after"} else "unordered"


def moment_choices(facts: list[Fact], chronology: Chronology) -> list[Hashable]:
    events = {e for f in facts if f.canonical for e in f.events}
    return sorted(events, key=lambda e: (sum(chronology.order(o, e) == "before" for o in events), str(e)))


def reconstruct(facts: list[Fact], subject_ids, kind: str, event, chronology: Chronology) -> State:
    """The state of `subject_ids` at `event` (None: unspecified) from claims already inside the reading boundary."""
    own = [f for f in facts if f.subject in subject_ids]
    if event is None:
        choices = moment_choices([f for f in own if f.explained], chronology)
        if len(choices) > 1:
            return State("needs_context", None, choices=choices)
        event = choices[0] if choices else None
    state = State("resolved", event)
    removed = [f for f in own if f.explained and f.polarity == "negated" and f.modality in CANONICAL_MODALITY
               and (event is None or position(f, event, chronology) in {"direct", "before"})]
    direct, carried = {}, {}
    for fact in own:
        if not fact.explained:
            state.excluded[fact.id] = "missing_assumption"
            continue
        if fact.modality not in CANONICAL_MODALITY:
            state.excluded[fact.id] = fact.modality
            continue
        if fact.polarity == "negated":
            state.excluded[fact.id] = "negated"
            continue
        key, item = fact.attribute.casefold(), part(fact.attribute)
        where = ("direct" if event is None else "untimed") if not fact.events else \
            "unordered" if event is None else position(fact, event, chronology)
        if where != "direct" and any(same(n.value, fact.value) and fact.events != n.events and (
                part(n.attribute) == item or attribute_key(n.attribute) == attribute_key(fact.attribute))
                for n in removed):
            state.excluded[fact.id] = "removed"
        elif where == "direct":
            direct.setdefault(key, []).append(fact)
        elif where == "after":
            state.excluded[fact.id] = "later in story time"
        elif where == "unordered":
            state.excluded[fact.id] = "order unknown"
        elif fact.kind == "scene":
            state.excluded[fact.id] = "scene-specific"
        elif where == "untimed" and fact.kind in UNTIMED or fact.kind == "acquired":
            carried.setdefault(item, []).append(fact)  # an inference at most
        else:
            state.excluded[fact.id] = "tied to another moment"

    # Disputes compare one exact attribute; "coat_color" and "coat_material" are two traits, not a conflict.
    for key, items in direct.items():
        canonical = [f for f in items if f.canonical]
        chosen = canonical or items
        values = sorted({f.value for f in chosen}, key=str.casefold)
        status = "canonical" if canonical else "inferred"
        if canonical and len({v.casefold() for v in values}) > 1:
            status = "disputed"
        assumptions = {f.assumption.strip() for f in chosen if f.assumption and f.assumption.strip()}
        reason = None
        if status == "inferred":
            reason = next(iter(assumptions)) if len(assumptions) == 1 else \
                "Multiple provider assumptions; these values are inferred rather than explicitly stated."
        state.traits[key] = Trait(key, status, values, [f.id for f in chosen], reason)
        for fact in items:
            if fact not in chosen:
                state.excluded[fact.id] = "weaker than explicit evidence here"
    # An earlier change to a part ("left_cheek_marked") never stands beside direct evidence on it ("left_cheek_scar").
    described = {part(key) for key in state.traits}
    for item, items in carried.items():
        if item in described:
            for fact in items:
                state.excluded[fact.id] = "superseded at this moment"
            continue
        latest = [f for f in items if not any(f is not g and f.events and g.events and all(
            chronology.order(e, h) == "before" for e in f.events for h in g.events) for g in items)]
        for fact in items:
            if fact not in latest:
                state.excluded[fact.id] = "superseded by a later change"
        if len({(f.attribute.casefold(), f.value.casefold()) for f in latest}) == 1:
            reason = ("stated without a story moment" if not latest[0].events
                      else "acquired earlier; no persistence to this moment is established")
            assumptions = sorted({f.assumption.strip() for f in latest if f.support == "inferred" and f.assumption})
            if assumptions:
                temporal = "inferred without a story moment" if not latest[0].events else reason
                assumption = assumptions[0] if len(assumptions) == 1 else "Multiple provider assumptions"
                available = 256 - len(temporal) - 2
                prefix = assumption if len(assumption) <= available else assumption[:available - 3] + "..."
                reason = f"{prefix}; {temporal}"
            key = latest[0].attribute.casefold()
            state.traits[key] = Trait(key, "inferred", [latest[0].value], [f.id for f in latest], reason)
        else:
            for fact in latest:
                state.excluded[fact.id] = "order of earlier changes unknown"
    known = {attribute_key(t.attribute) for t in state.traits.values() if t.status != "inferred"}
    state.unknown = [a for a in CORE.get(kind, ()) if a not in known]
    if not any(t.status in {"canonical", "disputed", "inferred"} for t in state.traits.values()):
        state.outcome = "insufficient_evidence"
    return state
