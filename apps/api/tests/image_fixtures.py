"""A synthetic image adapter; no request leaves the machine."""

from app.providers.images import Image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class SyntheticImages:
    provider, model = "synthetic", "fixture-v1"
    settings = {"route": "fixture", "size": "8x8", "negative_prompt": "not_sent"}

    def generate(self, prompt):
        return Image(PNG, "image/png")
