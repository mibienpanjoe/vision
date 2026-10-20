"""Find disagreeing canonical claims and summarise traits without averaging them away."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Claim:
    id: Hashable
    subject: Hashable
    attribute: str
    value: str
    kind: str
    events: frozenset
    canonical: bool


def same_value(a: Claim, b: Claim) -> bool:
    return a.value.casefold().strip() == b.value.casefold().strip()


def conflicts(claims: Iterable[Claim]) -> set[frozenset]:
    """Canonical claims on one subject/attribute that apply at a shared event, or two unscoped identity traits."""
    canonical = [c for c in claims if c.canonical]
    found = set()
    for a, b in combinations(canonical, 2):
        if a.subject != b.subject or a.attribute != b.attribute or same_value(a, b):
            continue
        if a.events & b.events or (not a.events and not b.events and a.kind == b.kind == "identity"):
            found.add(frozenset((a.id, b.id)))
    return found


def summarize(claims: Iterable[Claim], subject, event, attributes: Iterable[str]) -> dict[str, tuple]:
    """Per attribute at one event: ("known", value), ("disputed", values) or ("unknown", None)."""
    applicable = [c for c in claims if c.canonical and c.subject == subject and event in c.events]
    result = {}
    for attribute in attributes:
        values = sorted({c.value for c in applicable if c.attribute == attribute})
        result[attribute] = ("unknown", None) if not values else ("known", values[0]) if len(values) == 1 \
            else ("disputed", values)
    return result
