from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceItem(Base):
    """Immutable. Never updated, never deleted. A correction is a NEW row that
    sets `superseded_by` on the prior item (done in one transaction). The app DB
    role is granted no UPDATE/DELETE on this table (migration 0001)."""

    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)

    control_id: Mapped[str] = mapped_column(String(64), index=True)  # logical, not versioned
    field: Mapped[str] = mapped_column(String(128))

    source: Mapped[str] = mapped_column(String(32))          # AGENTWATCH|OTEL|MANUAL|API
    evidence_type: Mapped[str] = mapped_column(String(64))   # registry key
    trust_score: Mapped[int] = mapped_column(Integer)

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))   # client-supplied, guarded
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)  # server

    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    hash: Mapped[str] = mapped_column(String(64))

    # Pointer lives on the NEW row (→ the older item it replaces), so superseding
    # is a pure INSERT — never an UPDATE of the old row. Keeps the table strictly
    # append-only. "Current" evidence = items not referenced by any other item's
    # `supersedes`.
    supersedes: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_items.id"), nullable=True
    )
