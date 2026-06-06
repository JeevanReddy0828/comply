from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Framework(Base):
    __tablename__ = "frameworks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    version: Mapped[str] = mapped_column(String(128))
    jurisdiction: Mapped[str] = mapped_column(String(64))
    catalog_version: Mapped[str] = mapped_column(String(32))
    effective_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    requirements: Mapped[list[Requirement]] = relationship(back_populates="framework")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    framework_id: Mapped[str] = mapped_column(ForeignKey("frameworks.id"))
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    article_refs: Mapped[list] = mapped_column(JSONB, default=list)
    applies_to: Mapped[list] = mapped_column(JSONB, default=list)
    catalog_version: Mapped[str] = mapped_column(String(32))

    framework: Mapped[Framework] = relationship(back_populates="requirements")


class Control(Base):
    """Composite identity (control_id, version). The loader INSERTS a new row on
    a version bump; it never mutates an existing one. `is_current` flags the
    active version. Evidence references control_id (logical); assessments stamp
    the exact version evaluated."""

    __tablename__ = "controls"

    control_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(16))
    review_status: Mapped[str] = mapped_column(String(32))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    frameworks: Mapped[list] = mapped_column(JSONB, default=list)
    article_refs: Mapped[list] = mapped_column(JSONB, default=list)
    annex_refs: Mapped[list] = mapped_column(JSONB, default=list)
    catalog_version: Mapped[str] = mapped_column(String(32))

    evidence_requirements: Mapped[list[EvidenceRequirement]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )


class ControlRequirement(Base):
    """M2M: a specific control version satisfies a requirement."""

    __tablename__ = "control_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["control_id", "control_version"],
            ["controls.control_id", "controls.version"],
        ),
        UniqueConstraint(
            "control_id", "control_version", "requirement_id",
            name="uq_control_requirement",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(64))
    control_version: Mapped[int] = mapped_column(Integer)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id"))


class EvidenceRequirement(Base):
    """Embedded in a control version. Drives gap detection + scoring."""

    __tablename__ = "evidence_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["control_id", "control_version"],
            ["controls.control_id", "controls.version"],
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(64))
    control_version: Mapped[int] = mapped_column(Integer)

    type: Mapped[str] = mapped_column(String(32))        # TELEMETRY|DOCUMENT|ATTESTATION|CONFIG
    field: Mapped[str] = mapped_column(String(128))
    freshness_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_score: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=True)

    control: Mapped[Control] = relationship(back_populates="evidence_requirements")
