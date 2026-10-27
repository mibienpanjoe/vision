"""Opt-in OpenAI text inference. Only bounded excerpts, no tools, history or stored responses."""

import copy
import json
import os
import socket
import urllib.error
import urllib.request

from app.providers.contracts import (
    ProviderCall,
    ProviderInputTooLarge,
    ProviderRateLimited,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
    Usage,
)

EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}


def strict_schema(schema: dict) -> dict:
    """OpenAI requires all object properties, including fields defaulted by the domain schema."""
    schema = copy.deepcopy(schema)

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for key, value in node.items():
                if key in {"properties", "$defs"}:
                    for definition in value.values():
                        visit(definition)
                else:
                    visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema


class OpenAIResponses:
    provider = "openai"

    def __init__(self, key: str, model: str = "gpt-6-luna", effort: str = "none",
                 base_url: str = "https://api.openai.com/v1"):
        self._key, self.model, self.effort, self.base_url = key, model, effort, base_url.rstrip("/")
        self.configuration = {"endpoint": "responses-v1", "reasoning": effort, "schema": "strict-v1"}

    @classmethod
    def from_environment(cls):
        key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("VISION_OPENAI_MODEL", "gpt-6-luna").strip()
        effort = os.environ.get("VISION_OPENAI_REASONING", "none")
        if not key or not model or len(model) > 64 or effort not in EFFORTS:
            return None
        return cls(key, model, effort)

    def complete(self, call: ProviderCall) -> ProviderResult:
        body = {"model": self.model, "instructions": call.system,
                "input": [{"role": "user", "content": call.data}], "store": False,
                "reasoning": {"effort": self.effort}, "max_output_tokens": call.max_output_tokens,
                "text": {"format": {"type": "json_schema", "name": "output", "strict": True,
                                    "schema": strict_schema(call.output_schema)}}}
        request = urllib.request.Request(f"{self.base_url}/responses", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json", "User-Agent": "vision/0.1"})
        try:
            # One transport attempt: a lost response must not silently repeat a charged call.
            with urllib.request.urlopen(request, timeout=call.timeout_seconds) as response:
                payload = json.loads(response.read(4_000_000))
        except urllib.error.HTTPError as error:
            if error.code == 413:
                raise ProviderInputTooLarge() from None
            if error.code == 429:
                raise ProviderRateLimited() from None
            raise ProviderUnavailable() from None
        except TimeoutError:
            raise ProviderTimeout() from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeout() from None
            raise ProviderUnavailable() from None
        except (ValueError, OSError):
            raise ProviderUnavailable() from None
        return parse_response(payload)


def parse_response(payload) -> ProviderResult:
    try:
        usage = payload["usage"]
        counts = [usage["input_tokens"], usage["output_tokens"]]
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError()
        outcome = "succeeded"
        if payload["status"] != "completed":
            outcome = ("budget_exhausted" if (payload.get("incomplete_details") or {}).get("reason") ==
                       "max_output_tokens" else "provider_unavailable")
        parts = [part for item in payload["output"] if item["type"] == "message" for part in item["content"]]
        if any(part["type"] == "refusal" for part in parts):
            outcome = "provider_unavailable"
        output = "".join(part["text"] for part in parts if part["type"] == "output_text")
        return ProviderResult(output=output if outcome == "succeeded" else "", outcome=outcome,
            usage=Usage(input_tokens=counts[0], output_tokens=counts[1]), model_version=payload["model"])
    except (KeyError, TypeError, ValueError):
        raise ProviderUnavailable() from None
