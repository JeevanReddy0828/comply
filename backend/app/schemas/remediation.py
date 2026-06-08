from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED"}


class TaskCreate(BaseModel):
    control_id: str = Field(..., min_length=1, max_length=64)
    owner_id: str | None = None
    due_date: date | None = None
    notes: str = Field("", max_length=4000)


class TaskUpdate(BaseModel):
    # All optional; only fields actually sent are applied (model_fields_set), so an
    # explicit null unassigns owner / clears due_date, while omission means no change.
    status: str | None = None
    owner_id: str | None = None
    due_date: date | None = None
    notes: str | None = Field(None, max_length=4000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        return v


class TaskOut(BaseModel):
    id: str
    org_id: str
    system_id: str
    control_id: str
    status: str
    owner_id: str | None
    due_date: date | None
    notes: str
    source_gap_reason: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution: str | None

    model_config = ConfigDict(from_attributes=True)
