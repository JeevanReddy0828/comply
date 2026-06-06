from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    """Append-only, hash-chained. The app DB role is granted no UPDATE/DELETE on
    this table (migration 0001). `seq` gives deterministic chain order."""

    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), default=_uuid, unique=True)

    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))       # CREATE|UPDATE|SUPERSEDE|APPROVE|CLASSIFY|INGEST
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))

    payload_hash: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)  # ingested_at

    previous_hash: Mapped[str] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64))

    # Empty for now; future: ip, api_key_id, integration source, request_id, user_agent.
    # Not part of the integrity hash, so it can grow without affecting verification.
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
