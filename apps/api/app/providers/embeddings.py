"""Passage and query embedders behind one narrow interface.

`LocalEmbeddings` runs the pinned EmbeddingGemma-300M weights on this machine
(DEC-37), so passage text never leaves it. `HashedEmbeddings` is a deterministic
bag-of-words stand-in for tests; it proves scoping and versioning, not quality.
"""

import hashlib
import math
import re
from functools import cache
from importlib.metadata import version
from typing import Protocol

from app.models.embeddings import DIMENSION
from app.providers.local_entities import snapshot

GEMMA = ("google/embeddinggemma-300m", "57c266a740f537b4dc058e1b0cda161fd15afa75")
MAX_TOKENS = 512


class Embedder(Protocol):
    provider: str
    model: str  # names weights, revision, precision, runtime and window; part of the index version
    dimension: int

    def documents(self, texts: list[str]) -> list[list[float]]: ...

    def queries(self, texts: list[str]) -> list[list[float]]: ...


@cache
def gemma():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(snapshot(*GEMMA), device="cpu")
    model.max_seq_length = MAX_TOKENS
    return model


class LocalEmbeddings:
    provider = "local"
    dimension = DIMENSION

    def __init__(self):
        self.model = (f"embeddinggemma-300m@{GEMMA[1][:8]}/fp32/tok{MAX_TOKENS}/"
                      f"st{version('sentence-transformers')}/torch{version('torch').split('+')[0]}")

    def _encode(self, texts, prompt):
        if not texts:
            return []
        return gemma().encode(texts, prompt_name=prompt, normalize_embeddings=True, batch_size=16).tolist()

    def documents(self, texts):
        return self._encode(texts, "document")

    def queries(self, texts):
        return self._encode(texts, "query")


class HashedEmbeddings:
    provider = "deterministic"
    dimension = DIMENSION

    def __init__(self, model: str = "hashed-v1"):
        self.model = model

    def _vector(self, text):
        vector = [0.0] * DIMENSION
        for word in re.findall(r"\w+", text.casefold()):
            vector[int.from_bytes(hashlib.sha256(f"{self.model}:{word}".encode()).digest()[:4]) % DIMENSION] += 1
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def documents(self, texts):
        return [self._vector(t) for t in texts]

    def queries(self, texts):
        return [self._vector(t) for t in texts]
