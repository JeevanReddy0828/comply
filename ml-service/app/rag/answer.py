"""RAG query: local FAISS retrieval, optional Anthropic-generated answer.

Retrieval is always local. Answer generation is *advisory* and only runs when an
Anthropic API key is configured — otherwise we return the retrieved passages so
the caller can show grounded sources without an LLM. This is never part of
compliance scoring."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

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
    from openai import OpenAI  # imported only when a key is configured

    client = OpenAI(base_url=settings.nim_base_url, api_key=settings.nvidia_api_key)
    context = "\n\n".join(
        f"[{i + 1}] ({s['citation']}) {s['text']}" for i, s in enumerate(sources)
    )
    completion = client.chat.completions.create(
        model=settings.rag_answer_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}\n\n"
                "Answer using only the context above, with inline [n] citations.",
            },
        ],
        temperature=0.2,
        max_tokens=1024,
        # Nemotron is a reasoning model; keep thinking off for tight, grounded answers.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return (completion.choices[0].message.content or "").strip()


def answer(question: str, top_k: int | None = None) -> dict:
    k = top_k or settings.rag_top_k
    sources = _retrieve(question, k)

    if settings.nvidia_api_key:
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


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def stream(question: str, top_k: int | None = None) -> Iterator[str]:
    """Server-Sent Events stream: sources first, then reasoning + answer deltas.

    With thinking enabled, Nemotron emits reasoning_content before the answer, so
    streaming lets the UI show progress instead of a long blank wait."""
    k = top_k or settings.rag_top_k
    sources = _retrieve(question, k)
    yield _sse({"type": "sources", "sources": sources})

    if not settings.nvidia_api_key:
        yield _sse({"type": "done", "mode": "retrieval"})
        return

    try:
        from openai import OpenAI

        client = OpenAI(base_url=settings.nim_base_url, api_key=settings.nvidia_api_key)
        context = "\n\n".join(
            f"[{i + 1}] ({s['citation']}) {s['text']}" for i, s in enumerate(sources)
        )
        completion = client.chat.completions.create(
            model=settings.rag_answer_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nContext:\n{context}\n\n"
                    "Answer using only the context above, with inline [n] citations.",
                },
            ],
            temperature=0.2,
            max_tokens=4096,
            extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 4096},
            stream=True,
        )
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield _sse({"type": "reasoning", "delta": reasoning})
            if delta.content:
                yield _sse({"type": "answer", "delta": delta.content})
        yield _sse({"type": "done", "mode": "generated"})
    except Exception as e:
        log.warning("RAG stream generation failed (%s)", e)
        yield _sse({"type": "error", "message": f"Answer generation unavailable ({type(e).__name__})."})
        yield _sse({"type": "done", "mode": "retrieval"})
