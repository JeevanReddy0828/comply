"""Evidence ingestion: ingest -> normalize -> store -> audit. No compliance
evaluation here (that is Step 8). Immutable: every ingest is a pure INSERT;
superseding sets `supersedes` on the NEW row, never touches the old one."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.audit_actions import ENTITY_EVIDENCE, EVIDENCE_INGESTED, EVIDENCE_SUPERSEDED
from app.models import AISystem, EvidenceItem
from app.schemas.evidence import EvidenceCreate
from app.services.audit import append_event, compute_payload_hash
from app.services.evidence_registry import trust_score_for
from app.services.tenancy import scoped_get

CLOCK_SKEW = timedelta(minutes=5)
DEGRADED_AFTER = timedelta(days=365)  # coarse global staleness ceiling (not control-specific)


class EvidenceError(Exception):
    """Base for ingestion validation failures."""


class SystemNotFound(EvidenceError):
    pass


class UnknownEvidenceType(EvidenceError):
    pass


class InvalidCapturedAt(EvidenceError):
    pass


class InvalidSupersedes(EvidenceError):
    pass


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def ingest_evidence(
    db: Session, *, org_id: str, system_id: str, actor_id: str, data: EvidenceCreate
) -> EvidenceItem:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        raise SystemNotFound("System not found")

    trust = trust_score_for(data.evidence_type)
    if trust is None:
        raise UnknownEvidenceType(f"Unknown evidence_type: {data.evidence_type}")

    now = datetime.now(timezone.utc)
    captured = _as_utc(data.captured_at)
    if captured > now + CLOCK_SKEW:
        raise InvalidCapturedAt("captured_at is in the future")
    validity = "DEGRADED" if captured < now - DEGRADED_AFTER else "VALID"

    if data.supersedes:
        prior = scoped_get(db, EvidenceItem, org_id, data.supersedes)
        if prior is None or prior.system_id != system_id:
            raise InvalidSupersedes("superseded evidence not found in this system")
        action = EVIDENCE_SUPERSEDED
    else:
        action = EVIDENCE_INGESTED

    item = EvidenceItem(
        system_id=system_id,
        org_id=org_id,
        control_id=data.control_id,
        field=data.field,
        source=data.source,
        evidence_type=data.evidence_type,
        trust_score=trust,
        captured_at=captured,
        payload=data.payload,
        hash=compute_payload_hash(data.payload),
        supersedes=data.supersedes,
        validity_state=validity,
    )
    try:
        db.add(item)
        db.flush()
        append_event(
            db,
            actor=actor_id,
            action=action,
            entity_type=ENTITY_EVIDENCE,
            entity_id=item.id,
            payload={
                "system_id": system_id,
                "control_id": data.control_id,
                "evidence_type": data.evidence_type,
                "trust_score": trust,
                "validity_state": validity,
                "supersedes": data.supersedes,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(item)
    return item


def list_evidence(db: Session, *, org_id: str, system_id: str) -> list[EvidenceItem] | None:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        return None
    return (
        db.query(EvidenceItem)
        .filter(EvidenceItem.system_id == system_id, EvidenceItem.org_id == org_id)
        .order_by(EvidenceItem.ingested_at.desc())
        .all()
    )
