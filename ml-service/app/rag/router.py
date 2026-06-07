from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.rag import answer as answer_svc
from app.rag import store
from app.rag.schemas import RagQuery, RagResponse

router = APIRouter(prefix="/rag", tags=["rag"])


def _require_index() -> None:
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG index not built. Run `python -m app.rag.ingest`.",
        )


@router.post("/query", response_model=RagResponse)
def query(body: RagQuery) -> RagResponse:
    _require_index()
    return RagResponse(**answer_svc.answer(body.question, body.top_k))


@router.post("/query/stream")
def query_stream(body: RagQuery) -> StreamingResponse:
    _require_index()
    return StreamingResponse(
        answer_svc.stream(body.question, body.top_k),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/status")
def rag_status() -> dict:
    return {
        "index_built": store.exists(),
        "generation_enabled": bool(settings.nvidia_api_key),
        "answer_model": settings.rag_answer_model if settings.nvidia_api_key else None,
        "embedding_model": settings.embedding_model,
    }
