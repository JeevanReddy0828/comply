from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RagQuery(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20)


class RagSource(BaseModel):
    citation: str
    source: str
    score: float
    text: str


class RagResponse(BaseModel):
    mode: Literal["generated", "retrieval"]
    answer: str | None  # None in retrieval-only mode (no Anthropic key configured)
    sources: list[RagSource]
    note: str | None = None
