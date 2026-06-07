"""FAISS vector store + parallel metadata. Cosine similarity via inner product
on normalized embeddings."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

from app.config import settings
from app.rag.chunker import Chunk

_idx = None
_meta: list[dict] | None = None
_lock = threading.Lock()


def _paths() -> tuple[Path, Path]:
    d = Path(settings.index_dir)
    return d / "faiss.index", d / "meta.json"


def exists() -> bool:
    fi, mi = _paths()
    return fi.exists() and mi.exists()


def build(chunks: list[Chunk], embeddings: np.ndarray) -> None:
    import faiss

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    Path(settings.index_dir).mkdir(parents=True, exist_ok=True)
    fi, mi = _paths()
    faiss.write_index(index, str(fi))
    meta = [{"text": c.text, "citation": c.citation, "source": c.source} for c in chunks]
    mi.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _load():
    global _idx, _meta
    with _lock:
        if _idx is None:
            import faiss

            fi, mi = _paths()
            if not (fi.exists() and mi.exists()):
                raise FileNotFoundError("RAG index not built — run `python -m app.rag.ingest`")
            _idx = faiss.read_index(str(fi))
            _meta = json.loads(mi.read_text(encoding="utf-8"))
    return _idx, _meta


def search(query_embedding: np.ndarray, k: int) -> list[dict]:
    index, meta = _load()
    scores, ids = index.search(query_embedding, k)
    results: list[dict] = []
    for score, i in zip(scores[0], ids[0]):
        if i < 0:
            continue
        results.append({**meta[i], "score": float(score)})
    return results
