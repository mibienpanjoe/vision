"""Bounded provider execution returning validated output or a typed outcome.

Execution is side-effect free: callers persist the safe run record together with
any canonical writes, so a malformed or late response never reaches canon.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.model_runs import ModelRun
from app.providers.contracts import (
    Outcome,
    ProviderAdapter,
    ProviderRequest,
    ProviderTimeout,
    ProviderUnavailable,
    StructuredOutput,
    Usage,
    call_digest,
    compose,
)
from pydantic import ValidationError

ERROR_CODES: dict[Outcome, str | None] = {
    "succeeded": None, "invalid_output": "PROVIDER_INVALID_OUTPUT", "timeout": "PROVIDER_TIMEOUT",
    "budget_exhausted": "PROVIDER_BUDGET_EXHAUSTED", "cancelled": None,
    "provider_unavailable": "PROVIDER_UNAVAILABLE", "input_too_large": "PROVIDER_INPUT_TOO_LARGE",
}


@dataclass(frozen=True)
class RunRecord:
    """Safe metadata only: references, digests, versions and usage; no source text or responses."""
    role: str
    purpose: str
    provider: str
    model: str
    model_version: str | None
    prompt_version: str
    schema_version: str
    config: dict
    input_refs: list[str]
    input_sha256: str
    outcome: Outcome
    error_code: str | None
    usage: Usage | None
    started_at: datetime
    duration_ms: int


@dataclass(frozen=True)
class RunResult:
    record: RunRecord
    output: StructuredOutput | None = field(default=None)


def execute(adapter: ProviderAdapter, request: ProviderRequest, output: type[StructuredOutput],
            cancelled: Callable[[], bool] = lambda: False) -> RunResult:
    call = compose(request, output)
    started, clock = datetime.now(UTC), time.monotonic()
    usage, version, value = None, None, None

    def finish(outcome: Outcome) -> RunResult:
        record = RunRecord(role=request.role, purpose=request.purpose, provider=adapter.provider,
                           model=adapter.model, model_version=version, prompt_version=request.prompt_version,
                           schema_version=output.schema_version, config=request.limits.model_dump(),
                           input_refs=[item.ref for item in request.sources], input_sha256=call_digest(call),
                           outcome=outcome, error_code=ERROR_CODES[outcome], usage=usage, started_at=started,
                           duration_ms=round((time.monotonic() - clock) * 1000))
        return RunResult(record, value if outcome == "succeeded" else None)

    if cancelled():
        return finish("cancelled")
    if request.input_chars() > request.limits.max_input_chars:
        return finish("input_too_large")
    try:
        result = adapter.complete(call)
    except (ProviderTimeout, TimeoutError):
        return finish("timeout")
    except ProviderUnavailable:
        return finish("provider_unavailable")
    usage, version = result.usage, result.model_version
    if cancelled():
        return finish("cancelled")
    if time.monotonic() - clock > request.limits.timeout_seconds:
        return finish("timeout")
    if (usage.output_tokens > request.limits.max_output_tokens
            or usage.input_tokens + usage.output_tokens > request.limits.max_total_tokens):
        return finish("budget_exhausted")
    try:
        value = output.model_validate_json(result.output)
    except ValidationError:
        return finish("invalid_output")
    return finish("succeeded")


def persist_run(db, owner_id, record: RunRecord, generation_id=None) -> ModelRun:
    usage = record.usage
    run = ModelRun(owner_id=owner_id, generation_id=generation_id, role=record.role, purpose=record.purpose,
                   provider=record.provider, model=record.model, model_version=record.model_version,
                   prompt_version=record.prompt_version, schema_version=record.schema_version,
                   config=record.config, input_refs=record.input_refs, input_sha256=record.input_sha256,
                   outcome=record.outcome, error_code=record.error_code,
                   input_tokens=usage.input_tokens if usage else None,
                   output_tokens=usage.output_tokens if usage else None,
                   started_at=record.started_at, duration_ms=record.duration_ms)
    db.add(run)
    return run
