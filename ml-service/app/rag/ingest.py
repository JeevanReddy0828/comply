"""One-shot ingest: build corpus -> embed -> persist FAISS index.

    python -m app.rag.ingest
"""
from __future__ import annotations

from app.rag import corpus, embedder, store


def main() -> None:
    chunks = corpus.load_corpus()
    if not chunks:
        raise SystemExit("No corpus found. Check act_text_path and catalog_dir.")
    by_source: dict[str, int] = {}
    for c in chunks:
        by_source[c.source] = by_source.get(c.source, 0) + 1
    print(f"corpus: {len(chunks)} chunks {by_source}")
    print("embedding (first run downloads the embedding model)...")
    embeddings = embedder.embed([c.text for c in chunks])
    store.build(chunks, embeddings)
    print(f"index built: {embeddings.shape[0]} vectors, dim {embeddings.shape[1]} -> {store._paths()[0].parent}")


if __name__ == "__main__":
    main()
