"""Synthetic captures can be replayed without a provider or credentials."""

import pytest
from app.providers.contracts import ProviderCall, ProviderResult, Usage
from tests.reconstruction_trace import CaptureAdapter, ReplayAdapter


def test_capture_and_replay_preserve_the_full_result_and_reject_a_changed_request():
    class Adapter:
        provider, model, configuration = "synthetic", "example", {"reasoning": "none"}
        _key = "must-never-appear"

        def complete(self, call):
            return ProviderResult(output='{"facts":[]}', usage=Usage(input_tokens=10, output_tokens=5))

    call = ProviderCall(system="extract", data='{"sources":[]}', output_schema={"type": "object"},
                        max_output_tokens=100, timeout_seconds=10)
    capture = CaptureAdapter(Adapter())
    result = capture.complete(call)
    assert "must-never-appear" not in str(capture.calls)
    replay = ReplayAdapter(capture.calls)
    assert replay.complete(call) == result
    with pytest.raises(ValueError, match="request"):
        ReplayAdapter(capture.calls).complete(call.model_copy(update={"data": "changed"}))
    with pytest.raises(ValueError, match="exhausted"):
        replay.complete(call)


def test_call_budget_flags_a_blocked_attempt_but_not_an_exactly_filled_allowance():
    from app.providers.contracts import ProviderUnavailable
    from tests.reconstruction_trace import CallBudget
    budget = CallBudget(1)
    budget.take()
    assert budget.used == 1 and not budget.exhausted
    with pytest.raises(ProviderUnavailable):
        budget.take()
    assert budget.used == 1 and budget.exhausted
