"""Derive entities, exact mentions, aliases and relations for one source generation.

Provider calls run outside any transaction. Publication is all-or-nothing under
the derivation row lock: a failed, cancelled or superseded attempt writes only
its run lineage, and every accepted item is grounded in an exact passage span.
"""

import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from app.models.entities import (
    Entity,
    EntityAlias,
    EntityMention,
    EntityRelation,
    MentionCandidate,
)
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.models.works import Document, Work
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.execution import RunResult, execute, persist_run
from app.providers.extraction import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    EntityExtraction,
    entity_request,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

STAGE = "entities"


def processing_version(adapter: ProviderAdapter) -> str:
    return f"{PROMPT_VERSION}/{EntityExtraction.schema_version}/{adapter.provider}/{adapter.model}"[:160]


def batches(passages, limits: Limits):
    """Chapter-aligned groups that fit the request bounds; an oversized passage fails as input_too_large."""
    budget = limits.max_input_chars - len(INSTRUCTIONS)
    groups, current, size = [], [], 0
    for passage in passages:
        if current and (passage.chapter_ordinal != current[-1].chapter_ordinal
                        or size + len(passage.text) > budget or len(current) == 64):
            groups.append(current)
            current, size = [], 0
        current.append(passage)
        size += len(passage.text)
    return groups + [current] if current else groups


def claim(engine, generation_id, version):
    with Session(engine) as db, db.begin():
        generation = db.get(SourceGeneration, generation_id)
        document = db.get(Document, generation.document_id)
        owner_id = db.scalar(select(Work.owner_id).where(Work.id == document.work_id))
        derivation = db.scalar(select(Derivation).where(
            Derivation.generation_id == generation_id, Derivation.stage == STAGE,
            Derivation.processing_version == version).with_for_update())
        if derivation is not None and derivation.status == "succeeded":
            return derivation.id, None, owner_id, []
        if derivation is None:
            derivation = Derivation(generation_id=generation_id, stage=STAGE, processing_version=version,
                                    status="running", attempt=1, rejections={})
            db.add(derivation)
        else:
            derivation.status, derivation.error_code, derivation.completed_at = "running", None, None
            derivation.attempt += 1
        db.flush()
        passages = db.scalars(select(Passage).where(
            Passage.document_id == document.id, Passage.parser_revision == generation.parser_revision)
            .order_by(Passage.ordinal)).all()
        db.expunge_all()
        return derivation.id, derivation.attempt, owner_id, passages


def derive_entities(engine, generation_id: uuid.UUID, adapter: ProviderAdapter, limits: Limits = Limits(),
                    cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    derivation_id, attempt, owner_id, passages = claim(engine, generation_id, processing_version(adapter))
    if attempt is None:
        return derivation_id
    results: list[tuple[list[Passage], RunResult]] = []
    for group in batches(passages, limits):
        request = entity_request([SourceItem(ref=f"p{p.ordinal}", text=p.text) for p in group], limits)
        results.append((group, execute(adapter, request, EntityExtraction, cancelled)))
        if results[-1][1].output is None:
            break
    with Session(engine) as db, db.begin():
        derivation = db.scalar(select(Derivation).where(Derivation.id == derivation_id).with_for_update())
        if derivation.attempt != attempt or derivation.status != "running":
            return derivation_id
        runs = [persist_run(db, owner_id, result.record, generation_id, derivation_id) for _, result in results]
        db.flush()
        failed = next((result.record for _, result in results if result.output is None), None)
        if failed is not None:
            derivation.status = "cancelled" if failed.outcome == "cancelled" else "failed"
            derivation.error_code = failed.error_code
        else:
            derivation.rejections = publish(db, derivation_id, [(g, r.output, run.id) for (g, r), run in zip(results, runs)])
            derivation.status = "succeeded"
        derivation.completed_at = datetime.now(UTC)
    return derivation_id


def ground(passage, quote):
    start = passage.text.find(quote)
    return None if start < 0 else (start, start + len(quote))


def publish(db, derivation_id, outputs) -> dict:
    """Write grounded items; returns rejection counts by reason (no text)."""
    rejected: Counter[str] = Counter()
    entities: dict[tuple[str, str], Entity] = {}
    staged = []
    for group, output, run_id in outputs:
        by_ref = {f"p{p.ordinal}": p for p in group}
        declared = {}
        for item in output.entities:
            if item.key in declared:
                rejected["duplicate_key"] += 1
            else:
                declared[item.key] = item
        used, mentions, seen = set(), [], set()
        for item in output.mentions:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            keys = list(dict.fromkeys(([item.entity] if item.entity else []) + item.candidates))
            if passage is None or span is None:
                rejected["ungrounded"] += 1
            elif not keys or any(key not in declared for key in keys):
                rejected["unknown_entity"] += 1
            elif (passage.id, span) in seen:
                rejected["duplicate_mention"] += 1
            else:
                seen.add((passage.id, span))
                used.update(keys)
                mentions.append((passage, span, item.entity, keys))
        for key in declared:
            if key not in used:
                rejected["unmentioned_entity"] += 1
        local = {}
        for key in used:
            item = declared[key]
            identity = (item.kind, item.label.casefold())
            if identity not in entities:
                entities[identity] = Entity(id=uuid.uuid4(), derivation_id=derivation_id, kind=item.kind, label=item.label)
            local[key] = entities[identity]
        staged.append((by_ref, output, run_id, local, mentions))
    db.add_all(entities.values())
    db.flush()
    for by_ref, output, run_id, local, mentions in staged:
        for passage, (start, end), resolved, keys in mentions:
            mention = EntityMention(id=uuid.uuid4(), derivation_id=derivation_id, passage_id=passage.id, start=start,
                                    end=end, entity_id=local[resolved].id if resolved else None, model_run_id=run_id)
            db.add(mention)
            db.flush()
            db.add_all(MentionCandidate(mention_id=mention.id, entity_id=eid)
                       for eid in dict.fromkeys(local[key].id for key in keys))
        for item in output.aliases:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            if span is None or item.label.casefold() not in item.quote.casefold():
                rejected["ungrounded"] += 1
            elif item.entity not in local:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityAlias(entity_id=local[item.entity].id, label=item.label, status=item.status,
                                   passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
        for item in output.relations:
            passage = by_ref.get(item.ref)
            span = ground(passage, item.quote) if passage else None
            if span is None:
                rejected["ungrounded"] += 1
            elif item.subject not in local or item.object not in local or local[item.subject] is local[item.object]:
                rejected["unknown_entity"] += 1
            else:
                db.add(EntityRelation(derivation_id=derivation_id, subject_id=local[item.subject].id,
                                      relation=item.relation, object_id=local[item.object].id,
                                      passage_id=passage.id, start=span[0], end=span[1], model_run_id=run_id))
    return dict(rejected)
