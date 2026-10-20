"""Shared claim → bounded provider calls → guarded publication for derivation stages.

Provider calls run outside any transaction. Publication is all-or-nothing under
the derivation row lock and attempt counter: a failed, cancelled or superseded
attempt writes only its run lineage, and a succeeded derivation is never redone.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.models.works import Document, Work
from app.providers.contracts import (
    Limits,
    ProviderAdapter,
    ProviderRequest,
    StructuredOutput,
)
from app.providers.execution import RunResult, execute, persist_run
from sqlalchemy import select
from sqlalchemy.orm import Session

# A routed gateway may send one call to a weak or overloaded model; retry those outcomes a bounded number of times.
CALLS_PER_GROUP = 3
RETRYABLE = frozenset({"invalid_output", "provider_unavailable", "timeout"})


def processing_version(prompt_version: str, output: type[StructuredOutput], adapter: ProviderAdapter) -> str:
    return f"{prompt_version}/{output.schema_version}/{adapter.provider}/{adapter.model}"[:160]


def batches(passages, budget: int):
    """Chapter-aligned groups within a character budget; an oversized passage fails as input_too_large."""
    groups, current, size = [], [], 0
    for passage in passages:
        if current and (passage.chapter_ordinal != current[-1].chapter_ordinal
                        or size + len(passage.text) > budget or len(current) == 64):
            groups.append(current)
            current, size = [], 0
        current.append(passage)
        size += len(passage.text)
    return groups + [current] if current else groups


def ground(passage, quote):
    start = passage.text.find(quote)
    return None if start < 0 else (start, start + len(quote))


def claim(engine, generation_id, stage, version, input_id):
    with Session(engine) as db, db.begin():
        generation = db.get(SourceGeneration, generation_id)
        document = db.get(Document, generation.document_id)
        owner_id = db.scalar(select(Work.owner_id).where(Work.id == document.work_id))
        derivation = db.scalar(select(Derivation).where(
            Derivation.generation_id == generation_id, Derivation.stage == stage,
            Derivation.processing_version == version,
            Derivation.input_derivation_id.is_(None) if input_id is None
            else Derivation.input_derivation_id == input_id).with_for_update())
        if derivation is not None and derivation.status == "succeeded":
            return derivation.id, None, owner_id, []
        if derivation is None:
            derivation = Derivation(generation_id=generation_id, stage=stage, processing_version=version,
                                    input_derivation_id=input_id, status="running", attempt=1, rejections={})
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


def run_derivation(engine, generation_id: uuid.UUID, stage: str, adapter: ProviderAdapter,
                   output: type[StructuredOutput], prompt_version: str, limits: Limits,
                   build: Callable[[list[Passage], list[StructuredOutput]], ProviderRequest],
                   publish: Callable, budget: int, input_id: uuid.UUID | None = None,
                   cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    """`build` sees each passage group and the earlier groups' outputs; `publish` writes grounded rows."""
    version = processing_version(prompt_version, output, adapter)
    derivation_id, attempt, owner_id, passages = claim(engine, generation_id, stage, version, input_id)
    if attempt is None:
        return derivation_id
    results: list[tuple[list[Passage], RunResult]] = []  # every call, including retried failures
    accepted: list[tuple[list[Passage], RunResult]] = []
    for group in batches(passages, budget):
        request = build(group, [r.output for _, r in accepted])
        for _ in range(CALLS_PER_GROUP):
            result = execute(adapter, request, output, cancelled)
            results.append((group, result))
            if result.record.outcome not in RETRYABLE:
                break
        if result.output is None:
            break
        accepted.append((group, result))
    with Session(engine) as db, db.begin():
        derivation = db.scalar(select(Derivation).where(Derivation.id == derivation_id).with_for_update())
        if derivation.attempt != attempt or derivation.status != "running":
            return derivation_id
        runs = {id(result): persist_run(db, owner_id, result.record, generation_id, derivation_id)
                for _, result in results}
        db.flush()
        failed = results[-1][1].record if results and results[-1][1].output is None else None
        if failed is not None:
            derivation.status = "cancelled" if failed.outcome == "cancelled" else "failed"
            derivation.error_code = failed.error_code
        else:
            derivation.rejections = publish(db, derivation_id, [(g, r.output, runs[id(r)].id) for g, r in accepted])
            derivation.status = "succeeded"
        derivation.completed_at = datetime.now(UTC)
    return derivation_id
