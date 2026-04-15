"""Embedder interface + implementations.

Pluggable design:
    * HashEmbedder — zero-dep, deterministic, dùng cho demo/test/CI
    * VoyageEmbedder — Voyage AI (Anthropic partner) nếu có VOYAGE_API_KEY
    * SentenceTransformerEmbedder — local, multilingual, nếu đã cài

Hash embedder đủ dùng cho demo + test vì nó deterministic. Cho
production thực sự, nên bật Voyage hoặc sentence-transformers đa ngôn ngữ.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from typing import Protocol

log = logging.getLogger(__name__)


class Embedder(Protocol):
    """Interface tối thiểu cho một embedding backend."""

    dim: int

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


# --------------------------------------------------------------------------
# HashEmbedder — zero-dep fallback
# --------------------------------------------------------------------------

# Tách token để hỗ trợ tiếng Việt có dấu
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


class HashEmbedder:
    """Bag-of-hashed-words. Không mã hoá ngữ nghĩa sâu, nhưng khớp keyword
    chính xác đủ dùng cho demo, test, và CI không mạng.

    Deterministic: cùng input → cùng output, bất kể thời điểm.
    """

    def __init__(self, dim: int = 512, ngram: tuple[int, int] = (1, 2)):
        self.dim = dim
        self.ngram_min, self.ngram_max = ngram

    def _tokens(self, text: str) -> list[str]:
        return [t.lower() for t in _TOKEN_RE.findall(text or "")]

    def _features(self, text: str) -> list[str]:
        toks = self._tokens(text)
        feats: list[str] = list(toks)
        for n in range(max(2, self.ngram_min), self.ngram_max + 1):
            for i in range(len(toks) - n + 1):
                feats.append(" ".join(toks[i : i + n]))
        return feats

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feat in self._features(text):
            h = hashlib.sha256(feat.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0  # signed hashing giảm collision bias
            vec[idx] += sign
        # L2 normalize để cosine similarity = dot product
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


# --------------------------------------------------------------------------
# VoyageEmbedder — Anthropic's recommended embedding partner
# --------------------------------------------------------------------------

class VoyageEmbedder:
    """Voyage AI embedding backend. Cần VOYAGE_API_KEY + `pip install voyageai`.

    Dùng `voyage-multilingual-2` để hỗ trợ tiếng Việt tốt.
    """

    dim = 1024  # voyage-multilingual-2

    def __init__(self, model: str = "voyage-multilingual-2"):
        import voyageai  # type: ignore

        self.client = voyageai.Client()
        self.model = model

    def embed(self, text: str) -> list[float]:
        result = self.client.embed([text], model=self.model, input_type="document")
        return result.embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = self.client.embed(texts, model=self.model, input_type="document")
        return result.embeddings


# --------------------------------------------------------------------------
# SentenceTransformerEmbedder — local, multilingual
# --------------------------------------------------------------------------

class SentenceTransformerEmbedder:
    """Local sentence-transformers. Cần `pip install sentence-transformers`.

    Mặc định dùng `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, đa ngôn
    ngữ, gồm tiếng Việt).
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        import numpy as np  # sentence-transformers đã kéo numpy

        vec = self._model.encode(text, normalize_embeddings=True)
        return np.asarray(vec).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return np.asarray(vecs).tolist()


# --------------------------------------------------------------------------
# Default selector
# --------------------------------------------------------------------------

_DEFAULT: Embedder | None = None


def get_default_embedder() -> Embedder:
    """Chọn backend tốt nhất có sẵn. Ưu tiên:
        1. Voyage (nếu có VOYAGE_API_KEY + voyageai SDK)
        2. SentenceTransformer (nếu đã cài)
        3. HashEmbedder (luôn dùng được)
    """
    global _DEFAULT
    if _DEFAULT is not None:
        return _DEFAULT

    if os.environ.get("VOYAGE_API_KEY"):
        try:
            _DEFAULT = VoyageEmbedder()
            log.info("RAG dùng VoyageEmbedder.")
            return _DEFAULT
        except ImportError:
            log.debug("voyageai chưa cài, thử next.")

    if os.environ.get("HUMANARCHIVE_USE_SENTENCE_TRANSFORMERS"):
        try:
            _DEFAULT = SentenceTransformerEmbedder()
            log.info("RAG dùng SentenceTransformerEmbedder.")
            return _DEFAULT
        except ImportError:
            log.debug("sentence-transformers chưa cài, thử next.")

    _DEFAULT = HashEmbedder()
    log.info("RAG dùng HashEmbedder (zero-dep fallback — keyword match only).")
    return _DEFAULT
