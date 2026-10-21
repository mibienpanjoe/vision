"""Query-scoped consolidation (DEC-38): one provider call over the selected passages, then the existing gates.

The derivation's input is the entity derivation and its version carries the
digest of the scope (cutoff, subject, moment, context and exact passage spans),
so the same question over the same evidence reuses a succeeded consolidation
instead of calling the provider again. Every quote is grounded against the full
immutable passage before storage; events, facts and conflicts pass the T19/T20
publication code unchanged. Identity links stay inside this derivation, so they
never alter the local entity derivation or another reader's cutoff.
"""

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime

from app.models.entities import Entity, EntityRelation
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.providers.consolidation import (
    PROMPT_VERSION,
    Consolidation,
    consolidation_request,
)
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.execution import execute, persist_run
from app.services.narrative.derivations import claim, ground
from app.services.narrative.eligibility import latest
from app.services.narrative.events import publish_events
from app.services.narrative.visual_facts import publish_facts
from app.services.retrieval.query_plan import describe
from app.services.retrieval.rerank import Expanded
from sqlalchemy import select
from sqlalchemy.orm import Session

STAGE = "consolidation"
# About 20 passages / 5,000 tokens in (ADR-0003) and room for a combined answer, inside Groq's per-minute budget.
LIMITS = Limits(timeout_seconds=90, max_input_chars=24_000, max_output_tokens=4_096, max_total_tokens=12_000)
GAP = " … "


def scope_of(plan, expanded: Expanded) -> dict:
    spans = [[str(s.passage_id), start, end] for s in expanded.selection.passages for start, end in s.spans]
    spans += [[str(pid), 0, None] for pid in expanded.context]
    return {"cutoff": plan.cutoff, "subject": sorted(map(str, plan.subject.entity_ids)),
            "participants": sorted(str(i) for p in plan.participants for i in p.entity_ids),
            "moment": plan.moment.model_dump() if plan.moment else None, "context": plan.context,
            "creative_mode": plan.creative_mode, "spans": sorted(spans, key=lambda s: (s[0], s[1]))}


def request_item(plan) -> str:
    return json.dumps({"subject": plan.subject.label, "kind": plan.subject.kind,
                       "participants": [p.label for p in plan.participants],
                       "moment": describe(plan.moment) if plan.moment else None, "scene": plan.context},
                      ensure_ascii=False)


def consolidate(engine, plan, expanded: Expanded, adapter: ProviderAdapter, limits: Limits = LIMITS) -> uuid.UUID:
    with Session(engine) as db:
        entities = latest(db, plan.generation_id, "entities")
        if entities is None:
            raise ValueError("consolidation requires a succeeded entity derivation")
        ids = [s.passage_id for s in expanded.selection.passages] + expanded.context
        passages = {p.id: p for p in db.scalars(select(Passage).where(Passage.id.in_(ids)))}
        db.expunge_all()
    if any(p.document_id != plan.document_id or (plan.cutoff is not None and (p.chapter_ordinal or 0) > plan.cutoff)
           for p in passages.values()):
        raise ValueError("consolidation input must lie inside the plan's reading boundary")
    scope = scope_of(plan, expanded)
    digest = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    version = f"{PROMPT_VERSION}/{Consolidation.schema_version}/{adapter.provider}/{adapter.model}"[:140] + f"/{digest[:16]}"
    derivation_id, attempt, owner_id, _ = claim(engine, plan.generation_id, STAGE, version, entities.id,
                                                {**scope, "digest": digest})
    if attempt is None:
        return derivation_id

    texts = {s.passage_id: GAP.join(passages[s.passage_id].text[a:b] for a, b in s.spans)
             for s in expanded.selection.passages}
    texts.update({pid: passages[pid].text for pid in expanded.context})
    group = sorted((passages[pid] for pid in texts), key=lambda p: p.ordinal)
    request = consolidation_request([SourceItem(ref=f"p{p.ordinal}", text=texts[p.id]) for p in group],
                                    request_item(plan), limits)
    results = [execute(adapter, request, Consolidation)]
    if results[0].record.outcome == "invalid_output":  # one malformed answer gets one more call, no more
        results.append(execute(adapter, request, Consolidation))
    result = results[-1]

    with Session(engine) as db, db.begin():
        derivation = db.scalar(select(Derivation).where(Derivation.id == derivation_id).with_for_update())
        if derivation.attempt != attempt or derivation.status != "running":
            return derivation_id
        run = [persist_run(db, owner_id, r.record, plan.generation_id, derivation_id) for r in results][-1]
        db.flush()
        if result.output is None:
            derivation.status = "cancelled" if result.record.outcome == "cancelled" else "failed"
            derivation.error_code = result.record.error_code
        else:
            outputs = [(group, result.output, run.id)]
            keys: dict = {}
            rejected = Counter(publish_events(db, derivation_id, entities.id, outputs, keys))
            keyed = [(key, event.id, event.label, event.modality, 0, 0) for key, event in keys.items() if event]
            rejected.update(publish_facts(db, derivation_id, entities.id, keyed, outputs))
            rejected.update(publish_links(db, derivation_id, entities.id, group, result.output, run.id))
            requested = keys.get(result.output.requested_event) if result.output.requested_event else None
            if result.output.requested_event and requested is None:
                rejected["unknown_event"] += 1
            # Scope already holds the digest; the anchored moment is the stored event, never the model's key.
            derivation.scope = {**derivation.scope, "requested_event": str(requested.id) if requested else None}
            derivation.rejections = {reason: count for reason, count in rejected.items() if count}
            derivation.status = "succeeded"
        derivation.completed_at = datetime.now(UTC)
    return derivation_id


def publish_links(db, derivation_id, entity_derivation_id, group, output, run_id) -> Counter:
    """Quoted `same_as` links scoped to this consolidation; an unquoted identity is labelled inferred."""
    rejected: Counter[str] = Counter()
    labels = {e.label.casefold(): e.id for e in db.scalars(select(Entity).where(Entity.derivation_id == entity_derivation_id))}
    by_ref = {f"p{p.ordinal}": p for p in group}
    for link in output.identity_links:
        passage = by_ref.get(link.ref)
        span = ground(passage, link.quote) if passage else None
        subject, target = labels.get(link.subject.casefold()), labels.get(link.object.casefold())
        if span is None:
            rejected["ungrounded"] += 1
        elif subject is None or target is None or subject == target:
            rejected["unknown_entity"] += 1
        else:
            stated = link.support == "explicit" and all(n.casefold() in link.quote.casefold()
                                                        for n in (link.subject, link.object))
            db.add(EntityRelation(derivation_id=derivation_id, subject_id=subject,
                                  relation="same_as" if stated else "same_as_inferred", object_id=target,
                                  passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
    return rejected
