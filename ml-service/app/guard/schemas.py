from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GuardRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    identifier: str | None = Field(None, max_length=128, description="caller id for rate limiting")


class GuardReason(BaseModel):
    source: Literal["rule", "model"]
    detail: str
    severity: int | None = None
    score: float | None = None


class GuardVerdict(BaseModel):
    action: Literal["allow", "flag", "block"]
    blocked: bool
    risk_score: int  # 0-100
    injection_probability: float | None  # None if classifier unavailable
    classifier_available: bool
    reasons: list[GuardReason]
