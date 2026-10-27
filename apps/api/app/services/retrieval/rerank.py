"""Passage details for selection, and backward context expansion that cannot leave the boundary.

A description that starts with a pronoun, or a passage that never names the
subject, needs the text before it to attribute what it says. Expansion only
adds earlier passages of the same visible narrative, so it can never cross the
reading boundary; when the budget refuses one, the selection reports it.
"""

import re
import uuid
from dataclasses import dataclass

from app.services.retrieval.fusion import (
    SOURCES,
    Budget,
    PassageInfo,
    Selected,
    Selection,
)

PRONOUN_START = re.compile(r"\s*[\"“‘']?(he|she|they|it|his|her|their|its|him|them)\b", re.I)


@dataclass
class Expanded:
    selection: Selection
    context: list[uuid.UUID]  # earlier passages added only to attribute selected text
    unexpanded: int  # passages that needed context the budget could not hold


def needs_context(item: Selected, info: PassageInfo, anchors) -> bool:
    spans = item.protected or item.spans
    return not anchors or any(PRONOUN_START.match(info.text[start:end]) for start, end in spans)


def expand(selection: Selection, infos: dict[uuid.UUID, PassageInfo], anchors: dict[uuid.UUID, set],
           budget: Budget = Budget()) -> Expanded:
    by_ordinal = {info.ordinal: pid for pid, info in infos.items()}
    chosen = {s.passage_id for s in selection.passages}
    used = sum(end - start for s in selection.passages for start, end in s.spans)
    context, unexpanded = [], 0
    for item in selection.passages:
        info = infos[item.passage_id]
        if not needs_context(item, info, anchors.get(item.passage_id)):
            continue
        previous = by_ordinal.get(info.ordinal - 1)
        if previous is None or previous in chosen:
            continue
        size = len(infos[previous].text)
        if len(chosen) >= min(budget.passages, SOURCES) or used + size > budget.characters:
            unexpanded += 1
            continue
        chosen.add(previous)
        context.append(previous)
        used += size
    return Expanded(selection, context, unexpanded)
