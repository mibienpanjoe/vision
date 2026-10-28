"""Bounded opt-in Luna reasoning allowances; Groq and no-reasoning defaults stay intact."""

from app.providers.contracts import Limits, ProviderAdapter


def query_limits(adapter: ProviderAdapter | None, stage: str, default: Limits) -> Limits:
    effort = getattr(adapter, "configuration", {}).get("reasoning", "none")
    if getattr(adapter, "provider", None) != "openai" or adapter.model != "gpt-6-luna" or effort == "none":
        return default
    if stage == "consolidation":
        output, total, seconds = (8192, 24_000, 120) if effort == "low" else (16_384, 32_000, 180)
    elif stage == "adjudication":
        output, total, seconds = (4096, 16_000, 90) if effort == "low" else (8192, 24_000, 120)
    else:
        return default
    return default.model_copy(update={"max_output_tokens": output, "max_total_tokens": total,
                                      "timeout_seconds": seconds})
