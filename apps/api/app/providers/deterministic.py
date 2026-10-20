"""Reproducible adapters for contract tests; they prove plumbing, not extraction quality."""

import json
from collections.abc import Callable

from app.providers.contracts import ProviderCall, ProviderResult, Usage


def tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ScriptedAdapter:
    """Replays queued outputs or failures and records each call it received."""

    provider, model = "deterministic", "scripted-v1"

    def __init__(self, *responses: str | Exception, output_tokens: int | None = None):
        self.responses, self.output_tokens, self.calls = list(responses), output_tokens, []

    def complete(self, call: ProviderCall) -> ProviderResult:
        self.calls.append(call)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ProviderResult(output=response, model_version="1",
                              usage=Usage(input_tokens=tokens(call.system + call.data),
                                          output_tokens=self.output_tokens or tokens(response)))


class RuleAdapter:
    """Derives output from the data block with a pure function, independent of call order."""

    provider, model = "deterministic", "rule-v1"

    def __init__(self, rule: Callable[[list[dict]], dict], fail: Exception | None = None):
        self.rule, self.fail = rule, fail

    def complete(self, call: ProviderCall) -> ProviderResult:
        if self.fail is not None:
            raise self.fail
        output = json.dumps(self.rule(json.loads(call.data)["sources"]))
        return ProviderResult(output=output, model_version="1",
                              usage=Usage(input_tokens=tokens(call.system + call.data), output_tokens=tokens(output)))

