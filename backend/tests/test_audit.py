"""Audit ledger: append-once, tamper-evident, transaction-bound."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.models import AuditEvent, Organization
from app.services.audit import append_event, verify_chain


def _append(db, action, entity_id, payload=None):
    ev = append_event(
        db, actor="user1", action=action, entity_type="ai_system",
        entity_id=entity_id, payload=payload or {},
    )
    db.commit()
    return ev


# 1. Create entity → audit event exists
def test_append_creates_event(clean, db):
    _append(db, "SYSTEM_CREATED", "sys-1", {"name": "Acme"})
    assert db.query(AuditEvent).count() == 1
    assert verify_chain(db)["intact"] is True


# Chain links across multiple events
def test_chain_links_and_verifies(clean, db):
    _append(db, "SYSTEM_CREATED", "sys-1")
    _append(db, "EVIDENCE_INGESTED", "sys-1")
    _append(db, "ASSESSMENT_RUN", "sys-1")

    result = verify_chain(db)
    assert result["intact"] is True
    assert result["length"] == 3

    events = db.query(AuditEvent).order_by(AuditEvent.seq).all()
    assert events[0].previous_hash == "0" * 64
    assert events[1].previous_hash == events[0].current_hash
    assert events[2].previous_hash == events[1].current_hash


# 2. Update blocked → chain intact
def test_update_blocked_chain_intact(clean, db):
    _append(db, "SYSTEM_CREATED", "sys-1")
    with pytest.raises(DatabaseError):
        db.execute(text("UPDATE audit_events SET actor='hacker' WHERE entity_id='sys-1'"))
        db.flush()
    db.rollback()
    assert verify_chain(db)["intact"] is True


# 3. Tamper row → verification fails, identifies first broken event
def test_tamper_detected(clean, db):
    _append(db, "A", "sys-1")
    e2 = _append(db, "B", "sys-2")
    _append(db, "C", "sys-3")

    # Simulate an attacker with direct DB access (bypass the append-only trigger)
    db.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_append_only"))
    db.execute(text("UPDATE audit_events SET actor='hacker' WHERE seq=:s"), {"s": e2.seq})
    db.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_append_only"))
    db.commit()

    result = verify_chain(db)
    assert result["intact"] is False
    assert result["broken_at"]["seq"] == e2.seq
    assert "current_hash mismatch" in result["reason"]


# 4. Delete middle row → verification fails at the following row
def test_delete_detected(clean, db):
    _append(db, "A", "sys-1")
    e2 = _append(db, "B", "sys-2")
    e3 = _append(db, "C", "sys-3")

    db.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_append_only"))
    db.execute(text("DELETE FROM audit_events WHERE seq=:s"), {"s": e2.seq})
    db.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_append_only"))
    db.commit()

    result = verify_chain(db)
    assert result["intact"] is False
    # the row after the deleted one now has a dangling previous_hash
    assert result["broken_at"]["seq"] == e3.seq
    assert "previous_hash" in result["reason"]


# 5. Business write fails → no audit event (and no business row)
def test_business_failure_leaves_no_event(clean, db):
    try:
        with db.begin():
            org = Organization(name="ShouldRollback")
            db.add(org)
            db.flush()
            append_event(db, actor="u", action="ORG_CREATED", entity_type="org",
                         entity_id=org.id, payload={"name": org.name})
            raise RuntimeError("business op failed after audit append")
    except RuntimeError:
        pass

    assert db.query(AuditEvent).count() == 0
    assert db.query(Organization).filter(Organization.name == "ShouldRollback").count() == 0


# 6. Audit write fails → no business write
def test_audit_failure_rolls_back_business(clean, db, monkeypatch):
    import app.services.audit as audit_mod

    def boom(*a, **k):
        raise RuntimeError("audit append failed")

    monkeypatch.setattr(audit_mod, "append_event", boom)

    try:
        with db.begin():
            org = Organization(name="NeedsAudit")
            db.add(org)
            db.flush()
            audit_mod.append_event(db, actor="u", action="ORG_CREATED",
                                   entity_type="org", entity_id=org.id)
    except RuntimeError:
        pass

    assert db.query(Organization).filter(Organization.name == "NeedsAudit").count() == 0
    assert db.query(AuditEvent).count() == 0
