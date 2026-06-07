"""Local sentence-transformers embeddings (normalized for cosine via inner product)."""
from __future__ import annotations

import threading

import numpy as np

from app.config import settings

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    model = get_model()
    emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(emb, dtype="float32")
