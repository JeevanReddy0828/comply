from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ControlResultOut(BaseModel):
    control_id: str
    control_version: int
    status: str
    score: int
    freshness_grade: str | None
    evidence_count: int
    missing_requirements: list[dict]
    warnings: list[dict]

    model_config = ConfigDict(from_attributes=True)


class ComplianceOut(BaseModel):
    system_id: str
    assessment_id: str
    assessment_timestamp: datetime
    catalog_version: str
    applicability: str            # APPLICABLE | NOT_APPLICABLE
    system_score: int | None
    counts: dict
    results: list[ControlResultOut]


class GapsOut(BaseModel):
    system_id: str
    assessment_id: str
    gaps: list[ControlResultOut]


class AssessmentRunOut(ComplianceOut):
    pass
