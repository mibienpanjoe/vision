"""Retrieval candidates: exact passage spans with every path that found them.

Candidates are pointers into immutable passage text, deduplicated by span. A
protected candidate links the subject to a description cue; ranking may reorder
it but must never drop it for a low similarity score.
"""

import uuid
from dataclasses import dataclass, field

from app.schemas.scope import SourceSpan


@dataclass
class Candidate:
    passage_id: uuid.UUID
    start: int
    end: int
    paths: dict[str, int]  # retrieval path -> 1-based rank within that path
    protected: bool = False
    anchors: set[tuple[int, int]] = field(default_factory=set)  # subject mentions inside the span

    @property
    def key(self):
        return self.passage_id, self.start, self.end


def collect(*paths: list[Candidate]) -> list[Candidate]:
    """Union of candidates by exact span; ranks, protection and anchors are kept from every path."""
    merged: dict[tuple, Candidate] = {}
    for candidates in paths:
        for item in candidates:
            kept = merged.setdefault(item.key, Candidate(item.passage_id, item.start, item.end, {}))
            for path, rank in item.paths.items():
                kept.paths[path] = min(rank, kept.paths.get(path, rank))
            kept.protected |= item.protected
            kept.anchors |= item.anchors
    return list(merged.values())


def source_span(document_id: uuid.UUID, view, item: Candidate) -> SourceSpan:
    text = view.passages[item.passage_id][1]
    return SourceSpan(document_revision_id=str(document_id), passage_id=str(item.passage_id), start=item.start,
                      end=item.end, quote=text[item.start:item.end])
