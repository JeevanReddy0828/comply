from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RemediationTask(Base):
    """Operational remediation state for a control gap. Unlike evidence/audit,
    this is deliberately MUTABLE (status/owner/due change over a gap's life) — but
    every transition emits a hash-chained audit event, so the task's history is
    itself audit evidence.

    `control_id` is the logical id (unversioned), matching how evidence references
    controls. At most one non-RESOLVED task per (system, control) is enforced by a
    partial unique index, so the supersede-style history (resolved tasks + one open)
    survives a control regressing months later."""

    __tablename__ = "remediation_tasks"
    __table_args__ = (
        Index(
            "uq_open_task_per_control",
            "system_id",
            "control_id",
            unique=True,
            postgresql_where=text("status <> 'RESOLVED'"),
        ),
        Index("ix_remediation_tasks_system", "org_id", "system_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    control_id: Mapped[str] = mapped_column(String(64), index=True)  # logical, unversioned

    status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN|IN_PROGRESS|RESOLVED
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    # Why the gap existed when the task was opened — NO_EVIDENCE | BELOW_MIN_SCORE |
    # STALE (or MISSING). Captured at creation because the live control state may no
    # longer explain why the task was originally raised.
    source_gap_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user id or "system"
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)   # MANUAL | AUTO_SATISFIED
