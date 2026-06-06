from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrameworkOut(BaseModel):
    id: str
    name: str
    version: str
    jurisdiction: str
    catalog_version: str
    effective_date: str | None
    source_url: str | None

    model_config = ConfigDict(from_attributes=True)


class RequirementOut(BaseModel):
    id: str
    framework_id: str
    name: str
    description: str
    article_refs: list
    applies_to: list
    catalog_version: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceRequirementOut(BaseModel):
    type: str
    field: str
    freshness_seconds: int | None
    min_score: int
    required: bool

    model_config = ConfigDict(from_attributes=True)


class ControlSummaryOut(BaseModel):
    control_id: str
    version: int
    name: str
    confidence: str
    review_status: str
    frameworks: list
    article_refs: list
    annex_refs: list
    requirements: list[str]


class ControlDetailOut(ControlSummaryOut):
    description: str
    catalog_version: str
    evidence_requirements: list[EvidenceRequirementOut]
