from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.rag import answer as answer_svc
from app.rag import store
from app.rag.schemas import RagQuery, RagResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RagResponse)
def query(body: RagQuery) -> RagResponse:
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG index not built. Run `python -m app.rag.ingest`.",
        )
    return RagResponse(**answer_svc.answer(body.question, body.top_k))


@router.get("/status")
def rag_status() -> dict:
    return {
        "index_built": store.exists(),
        "generation_enabled": bool(settings.anthropic_api_key),
        "answer_model": settings.rag_answer_model if settings.anthropic_api_key else None,
        "embedding_model": settings.embedding_model,
    }
