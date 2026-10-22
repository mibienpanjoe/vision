"""D5 image adapters against a real local HTTP server; no request reaches a provider."""

import base64
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app.providers import images
from app.providers.images import (
    AcceptanceUnknown,
    HuggingFaceImages,
    OpenAIImages,
    RenderRejected,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def serve(reply):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            status, body = reply()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


@pytest.fixture
def gateway():
    servers = []

    def start(reply, timeout=5, gateway=HuggingFaceImages):
        server, seen = serve(reply)
        servers.append(server)
        return gateway("hf_synthetic", f"http://127.0.0.1:{server.server_port}", timeout), seen
    yield start
    for server in servers:
        server.shutdown()


@pytest.mark.parametrize(("name", "key", "model"), [("huggingface", "HF_TOKEN", "black-forest-labs/FLUX.1-schnell"),
                                                     ("openai", "OPENAI_API_KEY", "gpt-image-1")])
def test_policy_requires_explicit_opt_in_and_its_own_key(monkeypatch, name, key, model):
    for variable in ("VISION_RENDER_PROVIDER", "VISION_RENDER_MODEL", "HF_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(key, "synthetic-key")
    assert images.configured_policy() is None and images.image_adapter() is None
    monkeypatch.setenv("VISION_RENDER_PROVIDER", name)
    policy = images.configured_policy()
    assert (policy.provider, policy.model, policy.max_reservations_per_owner) == (name, model, 5)
    assert (images.image_adapter().provider, images.image_adapter().model) == (name, model)
    monkeypatch.delenv(key)
    monkeypatch.setenv("HF_TOKEN" if key == "OPENAI_API_KEY" else "OPENAI_API_KEY", "other-key")
    assert images.configured_policy() is None
    monkeypatch.setenv("VISION_RENDER_PROVIDER", "unknown")
    assert images.configured_policy() is None


def test_success_sends_only_the_prompt_and_returns_verified_image_bytes(gateway):
    adapter, seen = gateway(lambda: (200, json.dumps({"data": [{"b64_json": base64.b64encode(PNG).decode()}]}).encode()))
    image = adapter.generate("Arthur (hair: grey)")
    assert (image.data, image.media_type) == (PNG, "image/png")
    path, headers, body = seen[0]
    assert path == "/nscale/v1/images/generations" and headers["Authorization"] == "Bearer hf_synthetic"
    assert body == {"model": "black-forest-labs/FLUX.1-schnell", "prompt": "Arthur (hair: grey)",
                    "response_format": "b64_json", "size": "1024x1024"}


def test_only_approved_models_can_be_selected(monkeypatch):
    monkeypatch.setenv("VISION_RENDER_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("VISION_RENDER_MODEL", "gpt-image-2")
    assert images.configured_policy().model == images.image_adapter().model == "gpt-image-2"
    assert images.image_adapter().body("p")["model"] == "gpt-image-2"
    for unapproved in ("dall-e-3", "black-forest-labs/FLUX.1-schnell"):
        monkeypatch.setenv("VISION_RENDER_MODEL", unapproved)
        assert images.configured_policy() is None and images.image_adapter() is None


def test_openai_sends_low_quality_png_request_and_keeps_token_usage(gateway):
    reply = {"data": [{"b64_json": base64.b64encode(PNG).decode()}],
             "usage": {"input_tokens": 41, "output_tokens": 272, "total_tokens": 313, "note": "dropped"}}
    adapter, seen = gateway(lambda: (200, json.dumps(reply).encode()), gateway=OpenAIImages)
    image = adapter.generate("Arthur (hair: grey)")
    assert image.data == PNG and image.usage == {"input_tokens": 41, "output_tokens": 272, "total_tokens": 313}
    path, _, body = seen[0]
    assert path == "/v1/images/generations"
    assert body == {"model": "gpt-image-1", "prompt": "Arthur (hair: grey)", "n": 1, "size": "1024x1024",
                    "quality": "low", "output_format": "png"}


@pytest.mark.parametrize(("status", "error", "code"), [(429, "insufficient_quota", "PROVIDER_QUOTA_EXCEEDED"),
                                                       (400, "moderation_blocked", "PROVIDER_CONTENT_REFUSED"),
                                                       (429, "rate_limit_exceeded", "PROVIDER_RATE_LIMITED")])
def test_openai_error_codes_are_mapped_without_their_messages(gateway, status, error, code):
    body = json.dumps({"error": {"code": error, "message": "secret detail"}}).encode()
    adapter, _ = gateway(lambda: (status, body), gateway=OpenAIImages)
    with pytest.raises(RenderRejected) as raised:
        adapter.generate("prompt")
    assert raised.value.code == code and "secret" not in str(raised.value)


@pytest.mark.parametrize(("status", "code"), [(429, "PROVIDER_RATE_LIMITED"), (400, "PROVIDER_REJECTED"),
                                              (503, "PROVIDER_REJECTED"), (403, "PROVIDER_UNAUTHORIZED"),
                                              (401, "PROVIDER_UNAUTHORIZED"), (402, "PROVIDER_QUOTA_EXCEEDED")])
def test_http_refusals_are_definite_failures(gateway, status, code):
    adapter, _ = gateway(lambda: (status, b'{"error": "secret detail"}'))
    with pytest.raises(RenderRejected) as raised:
        adapter.generate("prompt")
    assert raised.value.code == code and "secret" not in str(raised.value)


@pytest.mark.parametrize("body", [b"not json", b'{"data": []}', json.dumps({"data": [{"b64_json": base64.b64encode(
    b"<svg/>").decode()}]}).encode()])
def test_accepted_but_unusable_output_is_a_definite_failure(gateway, body):
    adapter, _ = gateway(lambda: (200, body))
    with pytest.raises(RenderRejected) as raised:
        adapter.generate("prompt")
    assert raised.value.code == "PROVIDER_INVALID_OUTPUT"


def test_a_sent_request_without_a_response_is_acceptance_unknown(gateway):
    def slow():
        time.sleep(2)
        return 200, b"{}"
    adapter, seen = gateway(slow, timeout=0.5)
    with pytest.raises(AcceptanceUnknown):
        adapter.generate("prompt")
    assert len(seen) == 1


def test_refused_connection_never_reached_the_provider():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(RenderRejected) as raised:
        HuggingFaceImages("hf_synthetic", f"http://127.0.0.1:{port}", 2).generate("prompt")
    assert raised.value.code == "PROVIDER_UNAVAILABLE"
