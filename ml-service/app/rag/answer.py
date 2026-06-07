"""RAG query: local FAISS retrieval, optional Anthropic-generated answer.

Retrieval is always local. Answer generation is *advisory* and only runs when an
Anthropic API key is configured — otherwise we return the retrieved passages so
the caller can show grounded sources without an LLM. This is never part of
compliance scoring."""
from __future__ import annotations

import logging

from app.config import settings
from app.rag import embedder, store

log = logging.getLogger("rag.answer")

_SYSTEM = (
    "You are a EU AI Act compliance assistant. Answer the question USING ONLY the provided "
    "context passages. Cite the passages you use with their bracketed numbers, e.g. [1], [2]. "
    "If the context does not contain the answer, say so plainly — do not invent legal provisions "
    "or article numbers. Be concise and precise."
)


def _retrieve(question: str, k: int) -> list[dict]:
    return store.search(embedder.embed([question]), k)


def _generate(question: str, sources: list[dict]) -> str:
    import anthropic  # imported only when a key is configured

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    context = "\n\n".join(
        f"[{i + 1}] ({s['citation']}) {s['text']}" for i, s in enumerate(sources)
    )
    message = client.messages.create(
        model=settings.rag_answer_model,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}\n\n"
                "Answer using only the context above, with inline [n] citations.",
            }
        ],
    )
    return "".join(block.text for block in message.content if block.type == "text").strip()


def answer(question: str, top_k: int | None = None) -> dict:
    k = top_k or settings.rag_top_k
    sources = _retrieve(question, k)

    if settings.anthropic_api_key:
        try:
            return {"mode": "generated", "answer": _generate(question, sources), "sources": sources}
        except Exception as e:  # SDK missing, auth failure, rate limit, etc.
            log.warning("RAG generation failed (%s) — returning retrieval-only", e)
            return {
                "mode": "retrieval",
                "answer": None,
                "sources": sources,
                "note": f"Answer generation unavailable ({type(e).__name__}); showing top matches.",
            }

    return {"mode": "retrieval", "answer": None, "sources": sources}
