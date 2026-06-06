from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent, User
from app.security import require_capability
from app.services.audit import verify_chain
from app.services.auth import CAN_MANAGE_USERS, CAN_VIEW_COMPLIANCE

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify")
def verify(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    """Global chain integrity check."""
    return verify_chain(db)


@router.get("/events")
def list_events(
    entity_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    # Global ledger spans tenants; restrict raw listing to user managers for now.
    # Per-system, org-scoped views land with the systems router (Step 6).
    _: User = Depends(require_capability(CAN_MANAGE_USERS)),
):
    q = db.query(AuditEvent).order_by(AuditEvent.seq.desc())
    if entity_id:
        q = q.filter(AuditEvent.entity_id == entity_id)
    events = q.limit(min(limit, 500)).all()
    return [
        {
            "event_id": e.id,
            "seq": e.seq,
            "actor": e.actor,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "timestamp": e.timestamp.isoformat(),
            "current_hash": e.current_hash,
        }
        for e in events
    ]
