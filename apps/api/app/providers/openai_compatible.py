"""Live adapters for OpenAI-compatible chat APIs: the local FreeLLM gateway (DEC-24) and Groq (DEC-36).

Configuration comes from the environment; the key is sent only as a bearer
header and never appears in run records, errors or logs.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request

from app.providers.contracts import (
    ProviderCall,
    ProviderRateLimited,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
    Usage,
)

DEFAULT_BASE_URL = "http://127.0.0.1:3001/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
# Wait at most this long for a provider's advised retry before reporting the rate limit.
MAX_RETRY_WAIT = 20.0


class ChatGateway:
    provider = "freellm"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url, self._key, self.model = base_url.rstrip("/"), api_key, model

    @classmethod
    def from_environment(cls) -> "ChatGateway | None":
        key = os.environ.get("VISION_LLM_API_KEY")
        if not key:
            return None
        return cls(os.environ.get("VISION_LLM_BASE_URL", DEFAULT_BASE_URL), key,
                   os.environ.get("VISION_LLM_MODEL", "auto"))

    def response_format(self, call: ProviderCall) -> dict:
        return {"type": "json_object"}

    def complete(self, call: ProviderCall) -> ProviderResult:
        system = f"{call.system}\n\nRespond with one JSON object matching this JSON Schema:\n{json.dumps(call.output_schema)}"
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": call.max_output_tokens,
                           "response_format": self.response_format(call),
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": call.data}]}).encode()
        deadline = time.monotonic() + call.timeout_seconds
        for attempt in range(2):
            request = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                             headers={"Authorization": f"Bearer {self._key}",
                                                      "Content-Type": "application/json",
                                                      # Cloudflare-fronted gateways reject urllib's default agent (error 1010).
                                                      "User-Agent": "vision/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=max(1.0, deadline - time.monotonic())) as response:
                    payload = json.loads(response.read(4_000_000))
                break
            except urllib.error.HTTPError as error:
                if error.code != 429:
                    raise ProviderUnavailable() from None
                wait = retry_after(error.headers.get("retry-after"))
                # Honour the advised delay once, and only when the call's own time bound still allows it.
                if attempt or wait is None or wait > MAX_RETRY_WAIT or time.monotonic() + wait >= deadline:
                    raise ProviderRateLimited() from None
                time.sleep(wait)
            except TimeoutError:
                raise ProviderTimeout() from None
            except urllib.error.URLError as error:
                if isinstance(getattr(error, "reason", None), (TimeoutError, socket.timeout)):
                    raise ProviderTimeout() from None
                raise ProviderUnavailable() from None
            except (ValueError, OSError):
                raise ProviderUnavailable() from None
        try:
            content = payload["choices"][0]["message"]["content"] or ""
            usage = payload.get("usage") or {}
            return ProviderResult(output=strip_fence(content), model_version=str(payload.get("model", ""))[:64] or None,
                                  usage=Usage(input_tokens=usage.get("prompt_tokens", 0),
                                              output_tokens=usage.get("completion_tokens", 0)))
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderUnavailable() from None


class GroqGateway(ChatGateway):
    """Groq with Zero Data Retention (DEC-36): only cutoff-filtered excerpts at query time, never a whole book."""

    provider = "groq"

    @classmethod
    def from_environment(cls) -> "GroqGateway | None":
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            return None
        return cls(os.environ.get("VISION_GROQ_BASE_URL", GROQ_BASE_URL), key,
                   os.environ.get("VISION_GROQ_MODEL", GROQ_MODEL))

    def response_format(self, call: ProviderCall) -> dict:
        # Best-effort schema guidance; the envelope still validates every response strictly.
        return {"type": "json_schema", "json_schema": {"name": "output", "schema": call.output_schema, "strict": False}}


def retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


def strip_fence(text: str) -> str:
    """Some routed models wrap JSON in a Markdown fence despite json_object mode."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()
