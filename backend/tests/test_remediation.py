"""Remediation tasks: ownership + lifecycle over control gaps, with audited
auto-resolution when a re-assessment satisfies the control."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit_actions import ENTITY_TASK, TASK_CREATED, TASK_RESOLVED
from app.models import AISystem, AuditEvent, Organization, RemediationTask, User
from app.routers import assessments as assessments_router
from app.routers import auth as auth_router
from app.routers import remediation as remediation_router
from app.routers import systems as systems_router
from app.schemas.evidence import EvidenceCreate
from app.schemas.remediation import TaskCreate, TaskUpdate
from app.services.assessment import run_assessment
from app.services.audit import verify_chain
from app.services.auth import capabilities_for_role, hash_password
from app.services.evidence import ingest_evidence
from app.services.loader import load_catalog
from app.services.remediation import (
    DuplicateOpenTask,
    OwnerNotFound,
    UnknownControl,
    create_task,
    update_task,
)

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")


def _loaded(db):
    load_catalog(db, CATALOG)
    db.commit()


def _org_system(db, tier="HIGH"):
    org = Organization(name="Acme")
    db.add(org)
    db.flush()
    s = AISystem(org_id=org.id, name="Hiring Screener", intended_purpose="x",
                 deployment_context="automated_decision", risk_tier=tier,
                 classification={"risk_tier": tier})
    db.add(s)
    db.commit()
    db.refresh(s)
    return org, s


def _user(db, org_id, email, role="ComplianceOfficer"):
    u = User(org_id=org_id, email=email, password_hash=hash_password("supersecret1"),
             name=email.split("@")[0], role=role, capabilities=capabilities_for_role(role))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _ingest(db, system, field, etype, control_id):
    data = EvidenceCreate(control_id=control_id, field=field, source="AGENTWATCH",
                          evidence_type=etype, captured_at=datetime.now(timezone.utc), payload={"x": 1})
    return ingest_evidence(db, org_id=system.org_id, system_id=system.id, actor_id="tester", data=data)


def test_create_task_on_gap_captures_reason_and_audits(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "officer@acme.test")
    run_assessment(db, org_id=org.id, system_id=system.id, actor_id=actor.id)  # all MISSING

    task = create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id,
                       data=TaskCreate(control_id="LOG_001", owner_id=actor.id))

    assert task.status == "OPEN"
    assert task.owner_id == actor.id
    assert task.source_gap_reason == "NO_EVIDENCE"   # frozen from the assessment
    ev = db.query(AuditEvent).filter_by(action=TASK_CREATED, entity_id=task.id).one()
    assert ev.entity_type == ENTITY_TASK
    assert verify_chain(db)["intact"] is True


def test_one_open_task_per_control(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "o@acme.test")
    create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))
    with pytest.raises(DuplicateOpenTask):
        create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))
    assert db.query(RemediationTask).filter_by(system_id=system.id, control_id="LOG_001").count() == 1


def test_manual_status_transitions(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "o@acme.test")
    task = create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))

    task = update_task(db, org_id=org.id, task_id=task.id, actor_id=actor.id, data=TaskUpdate(status="IN_PROGRESS"))
    assert task.status == "IN_PROGRESS"
    assert task.resolved_at is None

    task = update_task(db, org_id=org.id, task_id=task.id, actor_id=actor.id, data=TaskUpdate(status="RESOLVED"))
    assert task.status == "RESOLVED"
    assert task.resolution == "MANUAL"
    assert task.resolved_by == actor.id
    assert task.resolved_at is not None
    assert db.query(AuditEvent).filter_by(action=TASK_RESOLVED, entity_id=task.id).count() == 1


def test_owner_must_be_in_org(clean, db):
    _loaded(db)
    org_a, system = _org_system(db)
    org_b = Organization(name="Other")
    db.add(org_b)
    db.flush()
    outsider = _user(db, org_b.id, "outsider@other.test")
    actor = _user(db, org_a.id, "a@acme.test")
    with pytest.raises(OwnerNotFound):
        create_task(db, org_id=org_a.id, system_id=system.id, actor_id=actor.id,
                    data=TaskCreate(control_id="LOG_001", owner_id=outsider.id))


def test_unknown_control_rejected(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "a@acme.test")
    with pytest.raises(UnknownControl):
        create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="NOPE_999"))


def test_auto_resolve_on_satisfied(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "a@acme.test")
    run_assessment(db, org_id=org.id, system_id=system.id, actor_id=actor.id)  # LOG_001 MISSING
    task = create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))

    _ingest(db, system, "decision_trace", "telemetry_trace", "LOG_001")  # now satisfies LOG_001
    run_assessment(db, org_id=org.id, system_id=system.id, actor_id=actor.id)

    db.refresh(task)
    assert task.status == "RESOLVED"
    assert task.resolution == "AUTO_SATISFIED"
    assert task.resolved_by == "system"
    assert db.query(AuditEvent).filter_by(action=TASK_RESOLVED, entity_id=task.id).count() == 1
    assert verify_chain(db)["intact"] is True


def test_resolved_then_new_open_allowed(clean, db):
    _loaded(db)
    org, system = _org_system(db)
    actor = _user(db, org.id, "a@acme.test")
    t1 = create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))
    update_task(db, org_id=org.id, task_id=t1.id, actor_id=actor.id, data=TaskUpdate(status="RESOLVED"))
    # a control can regress: a new open task is allowed once the prior one is resolved
    t2 = create_task(db, org_id=org.id, system_id=system.id, actor_id=actor.id, data=TaskCreate(control_id="LOG_001"))
    assert t2.id != t1.id
    statuses = {t.status for t in db.query(RemediationTask).filter_by(control_id="LOG_001").all()}
    assert statuses == {"RESOLVED", "OPEN"}


def test_endpoint_capability_tenancy_and_codes(clean, db):
    _loaded(db)  # catalog isn't auto-loaded without the app lifespan
    app = FastAPI()
    for r in (auth_router, systems_router, assessments_router, remediation_router):
        app.include_router(r.router)
    client = TestClient(app)

    tok = client.post("/auth/register", json={
        "organization_name": "Acme", "email": "admin@acme.test", "password": "supersecret1", "name": "Admin"
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = client.post("/systems", headers=h, json={"name": "S", "risk_tier": "HIGH"}).json()["id"]
    client.post(f"/assessments/run/{sid}", headers=h)

    # owner picker
    users = client.get("/auth/users", headers=h).json()
    assert any(u["email"] == "admin@acme.test" for u in users)

    created = client.post(f"/systems/{sid}/tasks", headers=h, json={"control_id": "LOG_001"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["source_gap_reason"] == "NO_EVIDENCE"

    assert len(client.get(f"/systems/{sid}/tasks", headers=h).json()) == 1
    # duplicate open task -> 409
    assert client.post(f"/systems/{sid}/tasks", headers=h, json={"control_id": "LOG_001"}).status_code == 409

    # cross-tenant: another org cannot see the task
    tok_b = client.post("/auth/register", json={
        "organization_name": "Beta", "email": "admin@beta.test", "password": "supersecret1", "name": "B"
    }).json()["access_token"]
    hb = {"Authorization": f"Bearer {tok_b}"}
    assert client.get(f"/tasks/{task_id}", headers=hb).status_code == 404
    assert client.patch(f"/tasks/{task_id}", headers=hb, json={"status": "RESOLVED"}).status_code == 404
