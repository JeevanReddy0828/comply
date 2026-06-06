from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SystemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    intended_purpose: str = Field("", max_length=4000)
    deployment_context: str = Field("", max_length=64)
    # Manual inputs until the Step-3 classifier lands; both optional.
    risk_tier: str | None = Field(None, max_length=32)
    annex_iii_category: str | None = Field(None, max_length=64)


class SystemOut(BaseModel):
    id: str
    org_id: str
    name: str
    intended_purpose: str
    deployment_context: str
    risk_tier: str | None
    annex_iii_category: str | None
    classification: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
