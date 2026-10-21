"""Derive atomic visual facts from one succeeded event derivation.

Before a fact is stored it must pass deterministic gates: a known subject named
or resolved as a mention in an evidence passage, grounded quotes, no explicit owner negation ("not
Arthur"), and for affirmed explicit claims a value word asserted outside a
question or a preceding negation. These are lexical guards, not entailment.
"""

import json
import re
import uuid
from collections import Counter
from collections.abc import Callable

from app.models.entities import Entity, EntityMention
from app.models.events import Event, EventEvidence
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.models.visual_facts import FactConflict, FactEvent, FactEvidence, VisualFact
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.visual_facts import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    FactExtraction,
    fact_request,
)
from app.services.narrative.derivations import ground, run_derivation
from app.services.reconstruction.conflicts import Claim, conflicts
from sqlalchemy import func, select
from sqlalchemy.orm import Session

STAGE = "facts"
KNOWN_BUDGET = 8_000
NEGATION = re.compile(r"\b(not|no|never|without|nor)\b|n't\b")
WORD = re.compile(r"[^\W\d_]{3,}")
STOP = {"the", "and", "with", "his", "her", "its", "their", "still", "possibly"}


def assertion_problem(value: str, quotes: list[str]) -> str | None:
    words = [w.casefold() for w in WORD.findall(value) if w.casefold() not in STOP]
    asserted = False
    for quote in quotes:
        for sentence in re.findall(r"[^.?!;]+[.?!;]?", quote):
            tokens = [t.casefold() for t in re.findall(r"[\w']+", sentence)]
            raw = re.findall(r"[\w']+", sentence)
            for i, token in enumerate(tokens):
                if token not in words:
                    continue
                window = [(tokens[j], raw[j + 1] if j + 1 < len(raw) else "") for j in range(max(0, i - 3), i)]
                negated = any(NEGATION.fullmatch(t) and not nxt[:1].isupper() for t, nxt in window)
                if not sentence.strip().endswith("?") and not negated:
                    asserted = True
    if not any(w in q.casefold() for q in quotes for w in words):
        return "value_ungrounded"
    return None if asserted else "negated_or_question"


def visible_events(db, event_derivation_id):
    """Events keyed `e:n` in source order with the chapter that first reveals them."""
    rows = db.execute(select(Event.id, Event.label, Event.modality, func.min(Passage.ordinal),
                             func.min(Passage.chapter_ordinal))
                      .join(EventEvidence, EventEvidence.event_id == Event.id)
                      .join(Passage, Passage.id == EventEvidence.passage_id)
                      .where(Event.derivation_id == event_derivation_id)
                      .group_by(Event.id).order_by(func.min(Passage.ordinal), Event.label, Event.id)).all()
    return [(f"e:{i}", *row) for i, row in enumerate(rows)]


def derive_visual_facts(engine, generation_id: uuid.UUID, event_derivation_id: uuid.UUID, adapter: ProviderAdapter,
                        limits: Limits = Limits(), cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    with Session(engine) as db:
        events = db.get(Derivation, event_derivation_id)
        if events is None or events.generation_id != uuid.UUID(str(generation_id)) or events.stage != "events" \
                or events.status != "succeeded":
            raise ValueError("facts require a succeeded event derivation of the same generation")
        entity_derivation_id = events.input_derivation_id
        keyed = visible_events(db, event_derivation_id)

    def build(group, _previous):
        chapter = group[-1].chapter_ordinal or 0
        listing, size = [], 2
        for key, _id, label, modality, _ordinal, first_chapter in keyed:
            entry = json.dumps({"key": key, "label": label, "modality": modality}, ensure_ascii=False)
            if (first_chapter or 0) <= chapter and size + len(entry) + 1 <= KNOWN_BUDGET:
                listing.append(entry)
                size += len(entry) + 1
        return fact_request([SourceItem(ref=f"p{p.ordinal}", text=p.text) for p in group],
                            f"[{','.join(listing)}]", limits)

    def publish(db, derivation_id, outputs):
        return publish_facts(db, derivation_id, entity_derivation_id, keyed, outputs)

    return run_derivation(engine, generation_id, STAGE, adapter, FactExtraction, PROMPT_VERSION, limits, build,
                          publish, limits.max_input_chars - len(INSTRUCTIONS) - KNOWN_BUDGET,
                          input_id=event_derivation_id, cancelled=cancelled)


def publish_facts(db, derivation_id, entity_derivation_id, keyed, outputs) -> dict:
    rejected: Counter[str] = Counter()
    subjects = {e.label.casefold(): e for e in db.scalars(select(Entity).where(Entity.derivation_id == entity_derivation_id))}
    mentioned = set(db.execute(select(EntityMention.entity_id, EntityMention.passage_id)
                               .where(EntityMention.derivation_id == entity_derivation_id)).all())
    stored: list[tuple[VisualFact, frozenset]] = []
    for group, output, run_id in outputs:
        by_ref = {f"p{p.ordinal}": p for p in group}
        chapter = group[-1].chapter_ordinal or 0
        events = {key: event_id for key, event_id, _l, _m, _o, first in keyed if (first or 0) <= chapter}
        for item in output.facts:
            subject = subjects.get(item.subject.casefold())
            spans = [(by_ref[e.ref], e.quote, ground(by_ref[e.ref], e.quote)) for e in item.evidence if e.ref in by_ref]
            spans = [(p, q, s) for p, q, s in spans if s is not None]
            quotes = [q for _, q, _ in spans]
            linked = frozenset(events[k] for k in item.events if k in events)
            if len(set(item.events)) > len(linked):
                rejected["unknown_event"] += len(set(item.events)) - len(linked)
            label = subject.label.casefold() if subject else ""
            if subject is None:
                problem = "unknown_subject"
            elif not spans:
                problem = "ungrounded"
            elif not any(label in p.text.casefold() or (subject.id, p.id) in mentioned for p, _, _ in spans):
                problem = "unattributed"
            elif any(f"not {label}" in q.casefold() for q in quotes):
                problem = "wrong_owner"
            elif item.support == "inferred" and not item.assumption:
                problem = "missing_assumption"
            elif item.kind == "scene" and not linked:
                problem = "unscoped_scene"
            elif item.support == "explicit" and item.polarity == "affirmed":
                problem = assertion_problem(item.value, quotes)
            else:
                problem = None
            if problem:
                rejected[problem] += 1
                continue
            fact = VisualFact(id=uuid.uuid4(), derivation_id=derivation_id, subject_id=subject.id,
                              attribute=item.attribute, value=item.value, kind=item.kind, support=item.support,
                              modality=item.modality, polarity=item.polarity, perspective=item.perspective,
                              assumption=item.assumption if item.support == "inferred" else None)
            db.add(fact)
            db.flush()
            db.add_all(FactEvidence(fact_id=fact.id, passage_id=p.id, start=s[0], end=s[1], model_run_id=run_id)
                       for p, s in dict.fromkeys((p, s) for p, _, s in spans))
            db.add_all(FactEvent(fact_id=fact.id, event_id=event_id) for event_id in linked)
            stored.append((fact, linked))
    claims = [Claim(f.id, f.subject_id, f.attribute, f.value, f.kind, linked, f.canonical) for f, linked in stored]
    for pair in conflicts(claims):
        a, b = sorted(pair)
        db.add(FactConflict(derivation_id=derivation_id, fact_a_id=a, fact_b_id=b, status="unresolved"))
    return {reason: count for reason, count in rejected.items() if count}
