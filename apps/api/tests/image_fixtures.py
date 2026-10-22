"""A synthetic image adapter returning a real, decodable PNG; no request leaves the machine."""

import struct
import zlib

from app.providers.images import Image


def png(width=8, height=8, rgb=(200, 150, 62)):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


PNG = png()


class SyntheticImages:
    provider, model = "synthetic", "fixture-v1"
    settings = {"route": "fixture", "size": "8x8", "negative_prompt": "not_sent"}

    def generate(self, prompt):
        return Image(PNG, "image/png")
