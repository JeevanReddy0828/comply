"""Tamper-evident audit ledger.

Invariant: every successful business operation emits exactly ONE audit event,
appended in the same transaction as the operation (see the `with db.begin()`
pattern in the routers). If the audit append fails, the business write rolls
back; if the business write fails, no audit event exists.

Hashing rule (locked):
    payload_hash  = sha256(canonical_json(payload))
    current_hash  = sha256(previous_hash | event_id | actor | action |
                           entity_type | entity_id | payload_hash)
Timestamp is deliberately NOT hashed (event_id already makes each event unique,
and timestamptz round-trips are not byte-stable). Canonical JSON is sorted and
compact so key order never changes the hash.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditEvent

GENESIS_HASH = "0" * 64


def _canonical(payload) -> str:
    return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_payload_hash(payload) -> str:
    return _sha(_canonical(payload))


def compute_current_hash(
    previous_hash: str,
    event_id: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload_hash: str,
) -> str:
    record = "|".join(
        [previous_hash, event_id, actor, action, entity_type, entity_id, payload_hash]
    )
    return _sha(record)


def append_event(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Append one event to the chain within the caller's transaction (flush only;
    the caller owns commit/rollback)."""
    last = db.query(AuditEvent).order_by(AuditEvent.seq.desc()).first()
    previous_hash = last.current_hash if last else GENESIS_HASH

    event_id = str(uuid.uuid4())
    payload_hash = compute_payload_hash(payload)
    current_hash = compute_current_hash(
        previous_hash, event_id, actor, action, entity_type, entity_id, payload_hash
    )

    event = AuditEvent(
        id=event_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_hash=payload_hash,
        timestamp=datetime.now(timezone.utc),
        previous_hash=previous_hash,
        current_hash=current_hash,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Walk the chain in insertion order; return integrity status and, on failure,
    the FIRST broken event with a reason."""
    events = db.query(AuditEvent).order_by(AuditEvent.seq.asc()).all()
    previous_hash = GENESIS_HASH

    for ev in events:
        if ev.previous_hash != previous_hash:
            return {
                "intact": False,
                "broken_at": {"seq": ev.seq, "event_id": ev.id},
                "reason": "previous_hash does not match prior event (missing or reordered row)",
                "verified": ev.seq - 1,
            }
        expected = compute_current_hash(
            ev.previous_hash, ev.id, ev.actor, ev.action,
            ev.entity_type, ev.entity_id, ev.payload_hash,
        )
        if expected != ev.current_hash:
            return {
                "intact": False,
                "broken_at": {"seq": ev.seq, "event_id": ev.id},
                "reason": "current_hash mismatch (row content tampered)",
                "verified": ev.seq - 1,
            }
        previous_hash = ev.current_hash

    return {
        "intact": True,
        "length": len(events),
        "head_hash": previous_hash,
        "broken_at": None,
    }
