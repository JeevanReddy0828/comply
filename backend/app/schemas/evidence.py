from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    control_id: str = Field(..., max_length=64)
    field: str = Field(..., max_length=128)
    source: Literal["AGENTWATCH", "OTEL", "MANUAL", "API"]
    evidence_type: str = Field(..., max_length=64)
    captured_at: datetime
    payload: dict = Field(default_factory=dict)
    supersedes: str | None = Field(None, max_length=36)


class EvidenceOut(BaseModel):
    id: str
    system_id: str
    control_id: str
    field: str
    source: str
    evidence_type: str
    trust_score: int
    validity_state: str
    captured_at: datetime
    ingested_at: datetime
    supersedes: str | None
    hash: str
    payload: dict

    model_config = ConfigDict(from_attributes=True)
