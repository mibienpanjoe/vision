"""Partial story-time order over stated event relations; never a forced total order.

Only fact and memory events take part: a dream, rumor, metaphor or hypothesis is
not a chronology update. Events on a stated cycle are inconsistent and are not
used as intermediates, so a contradiction cannot support a definite order.
"""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from typing import Literal

Order = Literal["before", "after", "overlaps", "unknown", "inconsistent"]
CHRONOLOGICAL = frozenset({"fact", "memory"})


@dataclass(frozen=True)
class Statement:
    source: Hashable
    relation: str
    target: Hashable


def close(nodes, before: set, contains: set) -> set:
    """Transitive closure of `before`; an event during another inherits its container's order."""
    closed = set(before)
    while True:
        added = {(a, c) for a, b in closed for b2, c in closed if b == b2 and a != c}
        added |= {(inner, c) for inner, outer in contains for o, c in closed if o == outer}
        added |= {(c, inner) for inner, outer in contains for c, o in closed if o == outer}
        if added <= closed:
            return closed
        closed |= added


class Chronology:
    def __init__(self, modality: dict, statements: Iterable[Statement]):
        self.eligible = {event for event, kind in modality.items() if kind in CHRONOLOGICAL}
        before, contains, self.overlapping = set(), set(), set()
        for s in statements:
            if s.source not in self.eligible or s.target not in self.eligible or s.source == s.target:
                continue
            if s.relation == "before":
                before.add((s.source, s.target))
            elif s.relation == "after":
                before.add((s.target, s.source))
            elif s.relation == "during":
                contains.add((s.source, s.target))
                self.overlapping |= {(s.source, s.target), (s.target, s.source)}
            elif s.relation == "overlaps":
                self.overlapping |= {(s.source, s.target), (s.target, s.source)}
        first = close(self.eligible, before, contains)
        self.cyclic = {a for a, b in first if (b, a) in first or a == b}
        keep = lambda pairs: {(a, b) for a, b in pairs if a not in self.cyclic and b not in self.cyclic}  # noqa: E731
        self.closed = close(self.eligible - self.cyclic, keep(before), keep(contains))

    def order(self, a, b) -> Order:
        if a not in self.eligible or b not in self.eligible or a == b:
            return "unknown"
        if a in self.cyclic or b in self.cyclic:
            return "inconsistent"
        ab, ba, overlap = (a, b) in self.closed, (b, a) in self.closed, (a, b) in self.overlapping
        if (ab and ba) or (overlap and (ab or ba)):
            return "inconsistent"
        return "before" if ab else "after" if ba else "overlaps" if overlap else "unknown"

    def inconsistencies(self) -> set:
        return {frozenset((a, b)) for a in self.eligible for b in self.eligible
                if a != b and self.order(a, b) == "inconsistent"}
