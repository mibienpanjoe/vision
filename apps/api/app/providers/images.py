"""D5 image providers (DEC-51), opt-in only: OpenAI gpt-image-2 or FLUX.1-schnell through the Hugging Face router.

Only the specification's composed prompt leaves the machine, never source text,
spans, titles or owner identifiers. The key is sent only as a bearer header.
Calls are charged and carry no provider idempotency key, so a request that may
have been sent is reported as acceptance unknown and never repeated.
"""

import base64
import binascii
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

SIZE = "1024x1024"
TIMEOUT_SECONDS = 120.0
MAX_IMAGE_BYTES = 16 * 1024 * 1024
# D5 acceptance cap: at most five live requests per owner.
MAX_RESERVATIONS = 5
REFUSALS = {401: "PROVIDER_UNAUTHORIZED", 403: "PROVIDER_UNAUTHORIZED", 402: "PROVIDER_QUOTA_EXCEEDED",
            429: "PROVIDER_RATE_LIMITED"}
# Provider error codes worth distinguishing; any other refusal text is discarded.
ERROR_CODES = {"insufficient_quota": "PROVIDER_QUOTA_EXCEEDED", "billing_hard_limit_reached": "PROVIDER_QUOTA_EXCEEDED",
               "moderation_blocked": "PROVIDER_CONTENT_REFUSED"}


@dataclass(frozen=True)
class RenderPolicy:
    provider: str
    model: str
    max_reservations_per_owner: int


@dataclass(frozen=True)
class Image:
    data: bytes
    media_type: str
    usage: dict | None = None


class RenderRejected(Exception):
    """The provider definitely produced no usable image; the code is safe to store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AcceptanceUnknown(Exception):
    """The request may have reached the provider and been charged."""


def media_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def refusal(error: urllib.error.HTTPError) -> str:
    try:
        code = json.loads(error.read(65_536))["error"]["code"]
    except (ValueError, KeyError, TypeError, OSError):
        code = None
    return ERROR_CODES.get(code) or REFUSALS.get(error.code, "PROVIDER_REJECTED")


def usage_counts(payload) -> dict | None:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    return {name: value for name in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(value := usage.get(name), int)} or None


class ImageGateway:
    """An OpenAI-style `images/generations` call answered with `data[0].b64_json`."""

    provider: str
    model: str
    base_url: str
    path: str
    settings: dict

    def __init__(self, token: str, base_url: str | None = None, timeout: float = TIMEOUT_SECONDS,
                 model: str | None = None):
        self._token, self.timeout = token, timeout
        self.base_url, self.model = (base_url or self.base_url).rstrip("/"), model or self.model

    def body(self, prompt: str) -> dict:
        raise NotImplementedError

    def generate(self, prompt: str) -> Image:
        request = urllib.request.Request(f"{self.base_url}{self.path}", data=json.dumps(self.body(prompt)).encode(),
                                         method="POST", headers={"Authorization": f"Bearer {self._token}",
                                                                 "Content-Type": "application/json",
                                                                 "User-Agent": "vision/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_IMAGE_BYTES * 2)
        except urllib.error.HTTPError as error:
            raise RenderRejected(refusal(error)) from None
        except urllib.error.URLError as error:
            # Only a failure before a connection existed proves nothing was sent.
            if isinstance(error.reason, (ConnectionRefusedError, socket.gaierror)):
                raise RenderRejected("PROVIDER_UNAVAILABLE") from None
            raise AcceptanceUnknown() from None
        except (TimeoutError, OSError):
            raise AcceptanceUnknown() from None
        try:
            payload = json.loads(raw)
            data = base64.b64decode(payload["data"][0]["b64_json"], validate=True)
        except (ValueError, KeyError, IndexError, TypeError, binascii.Error):
            raise RenderRejected("PROVIDER_INVALID_OUTPUT") from None
        kind = media_type(data)
        if kind is None or len(data) > MAX_IMAGE_BYTES:
            raise RenderRejected("PROVIDER_INVALID_OUTPUT")
        return Image(data, kind, usage_counts(payload))


class OpenAIImages(ImageGateway):
    provider, model = "openai", "gpt-image-2"
    base_url, path = "https://api.openai.com", "/v1/images/generations"
    # GPT image models take no negative prompt; exclusions are not sent.
    settings = {"size": SIZE, "quality": "low", "output_format": "png", "negative_prompt": "not_sent"}

    def body(self, prompt):
        return {"model": self.model, "prompt": prompt, "n": 1, "size": SIZE, "quality": "low", "output_format": "png"}


class HuggingFaceImages(ImageGateway):
    provider, model = "huggingface", "black-forest-labs/FLUX.1-schnell"
    base_url, path = "https://router.huggingface.co", "/nscale/v1/images/generations"
    # FLUX.1-schnell is guidance-distilled and takes no negative prompt; exclusions are not sent.
    settings = {"route": "nscale", "size": SIZE, "negative_prompt": "not_sent"}

    def body(self, prompt):
        return {"model": self.model, "prompt": prompt, "response_format": "b64_json", "size": SIZE}


PROVIDERS = {"openai": ("OPENAI_API_KEY", OpenAIImages), "huggingface": ("HF_TOKEN", HuggingFaceImages)}
# Maintainer-approved models per provider (DEC-51); the first is the default, anything else disables rendering.
MODELS = {"openai": ("gpt-image-2", "gpt-image-1"), "huggingface": ("black-forest-labs/FLUX.1-schnell",)}


def selected() -> tuple[str, str] | None:
    name = os.environ.get("VISION_RENDER_PROVIDER", "")
    if name not in PROVIDERS or not os.environ.get(PROVIDERS[name][0]):
        return None
    model = os.environ.get("VISION_RENDER_MODEL") or MODELS[name][0]
    return (name, model) if model in MODELS[name] else None


def configured_policy() -> RenderPolicy | None:
    choice = selected()
    return RenderPolicy(*choice, MAX_RESERVATIONS) if choice else None


def image_adapter() -> ImageGateway | None:
    if (choice := selected()) is None:
        return None
    key, gateway = PROVIDERS[choice[0]]
    return gateway(os.environ[key], model=choice[1])
