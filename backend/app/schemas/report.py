"""Annex IV technical-documentation report. A read-only projection of a system's
latest assessment, reconstructed at the frozen assessment timestamp so every
control status and the evidence backing it is self-proving (invariant #8).

DRAFT until every feeding control is LEGAL_APPROVED — never presented as
validated conformity (review_methodology.md)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportEvidence(BaseModel):
    id: str
    field: str
    evidence_type: str
    source: str
    trust_score: int
    captured_at: datetime
    hash: str


class ReportControl(BaseModel):
    control_id: str
    control_version: int
    control_hash: str | None
    name: str
    status: str
    score: int
    review_status: str
    confidence: str
    missing_requirements: list[dict]
    evidence: list[ReportEvidence]


class ReportSection(BaseModel):
    section: int
    title: str
    content_source: str | None
    fields: list[str]
    controls: list[ReportControl]


class ReportSystem(BaseModel):
    id: str
    name: str
    intended_purpose: str
    deployment_context: str
    risk_tier: str | None
    annex_iii_category: str | None


class AnnexIVReport(BaseModel):
    system: ReportSystem
    applicability: str                     # APPLICABLE | NOT_APPLICABLE
    assessment_id: str
    assessment_timestamp: datetime
    catalog_version: str
    generated_at: datetime
    system_score: int | None
    counts: dict
    watermark: str                         # DRAFT | LEGAL_APPROVED
    note: str | None                       # set when Annex IV is not required
    sections: list[ReportSection]
