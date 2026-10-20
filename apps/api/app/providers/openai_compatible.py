"""Live adapter for an OpenAI-compatible chat gateway (the local FreeLLM API, DEC-24).

Configuration comes from the environment; the key is sent only as a bearer
header and never appears in run records, errors or logs.
"""

import json
import os
import socket
import urllib.error
import urllib.request

from app.providers.contracts import (
    ProviderCall,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
    Usage,
)

DEFAULT_BASE_URL = "http://127.0.0.1:3001/v1"


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

    def complete(self, call: ProviderCall) -> ProviderResult:
        system = f"{call.system}\n\nRespond with one JSON object matching this JSON Schema:\n{json.dumps(call.output_schema)}"
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": call.max_output_tokens,
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": call.data}]}).encode()
        request = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                         headers={"Authorization": f"Bearer {self._key}",
                                                  "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=call.timeout_seconds) as response:
                payload = json.loads(response.read(4_000_000))
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


def strip_fence(text: str) -> str:
    """Some routed models wrap JSON in a Markdown fence despite json_object mode."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()
