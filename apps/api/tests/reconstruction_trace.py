"""Opt-in synthetic evaluation tooling. Never installed in the application path."""

from app.providers.contracts import ProviderResult, ProviderUnavailable, call_digest


class CallBudget:
    def __init__(self, limit):
        self.limit, self.used, self.exhausted = limit, 0, False

    def take(self):
        if self.used >= self.limit:
            self.exhausted = True
            raise ProviderUnavailable()
        self.used += 1


class CaptureAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.provider, self.model = adapter.provider, adapter.model
        self.configuration = getattr(adapter, "configuration", {})
        self.calls = []

    def complete(self, call):
        entry = {"request": call.model_dump(), "digest": call_digest(call)}
        self.calls.append(entry)
        try:
            result = self.adapter.complete(call)
        except Exception as error:
            entry["error_type"] = type(error).__name__
            raise
        entry["response"] = result.model_dump()
        return result


class ReplayAdapter:
    provider, model = "synthetic", "replay-v1"

    def __init__(self, calls):
        self.calls, self.position = calls, 0

    def complete(self, call):
        if self.position >= len(self.calls):
            raise ValueError("Replay exhausted")
        entry = self.calls[self.position]
        if entry["digest"] != call_digest(call):
            raise ValueError("Replay request differs from captured request")
        self.position += 1
        if "error_type" in entry:
            from app.providers import contracts
            error = getattr(contracts, entry["error_type"], None)
            if error in {contracts.ProviderUnavailable, contracts.ProviderTimeout,
                         contracts.ProviderRateLimited, contracts.ProviderInputTooLarge}:
                raise error()
            raise ValueError("Captured unexpected failure; inspect the synthetic run")
        return ProviderResult.model_validate(entry["response"])
