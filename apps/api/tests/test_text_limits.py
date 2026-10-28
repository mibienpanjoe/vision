"""Reasoning has a bounded allowance independent of Groq's free-tier limits."""

from types import SimpleNamespace

import pytest
from app.providers.contracts import Limits
from app.providers.text_limits import query_limits


@pytest.mark.parametrize("provider,effort,output", [("groq", "medium", 4096), ("openai", "none", 4096),
                                                   ("openai", "low", 8192), ("openai", "medium", 16384)])
def test_consolidation_allowance_is_provider_and_effort_specific(provider, effort, output):
    default = Limits(max_input_chars=24_000, max_output_tokens=4096, max_total_tokens=12_000)
    adapter = SimpleNamespace(provider=provider, model="gpt-6-luna", configuration={"reasoning": effort})
    limits = query_limits(adapter, "consolidation", default)
    assert limits.max_output_tokens == output and limits.max_input_chars == default.max_input_chars
    assert limits.max_total_tokens >= limits.max_output_tokens
    assert default.max_output_tokens == 4096


def test_adjudication_and_explicit_non_luna_models_keep_separate_bounds():
    default = Limits(max_output_tokens=2048)
    adapter = SimpleNamespace(provider="openai", model="gpt-6-luna", configuration={"reasoning": "medium"})
    assert query_limits(adapter, "adjudication", default).max_output_tokens == 8192
    adapter.model = "explicit-other-model"
    assert query_limits(adapter, "adjudication", default) == default


def test_reasoning_timeouts_leave_a_margin_inside_the_browser_proxy():
    adapter = SimpleNamespace(provider="openai", model="gpt-6-luna", configuration={"reasoning": "medium"})
    default = Limits()
    assert sum(query_limits(adapter, stage, default).timeout_seconds
               for stage in ("consolidation", "adjudication")) <= 240
