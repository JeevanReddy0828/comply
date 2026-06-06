from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    catalog_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    results: Mapped[list[AssessmentResult]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentResult(Base):
    """Per-control outcome. Stamps the exact control_version evaluated so the
    report is reproducible after the catalog evolves."""

    __tablename__ = "assessment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)

    control_id: Mapped[str] = mapped_column(String(64))
    control_version: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(16))   # SATISFIED|PARTIAL|MISSING
    score: Mapped[int] = mapped_column(Integer, default=0)
    freshness_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_requirements: Mapped[list] = mapped_column(JSONB, default=list)

    assessment: Mapped[Assessment] = relationship(back_populates="results")
