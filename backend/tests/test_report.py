"""Annex IV report assembly: a read-only projection of the latest assessment,
evidence-traced and DRAFT-watermarked."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit_actions import ASSESSMENT_RUN
from app.models import AISystem, AuditEvent, Organization
from app.routers import assessments as assessments_router
from app.routers import auth as auth_router
from app.routers import systems as systems_router
from app.schemas.evidence import EvidenceCreate
from app.services.assessment import run_assessment
from app.services.evidence import ingest_evidence
from app.services.loader import load_catalog
from app.services.report import NoAssessment, build_annex_iv

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")


def _loaded(db):
    load_catalog(db, CATALOG)
    db.commit()


def _system(db, tier="HIGH"):
    org = Organization(name="Acme")
    db.add(org)
    db.flush()
    s = AISystem(org_id=org.id, name="Hiring Screener", intended_purpose="rank applicants",
                 deployment_context="automated_decision", risk_tier=tier,
                 classification={"risk_tier": tier, "method": "manual_input", "confidence": 0.5})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _ingest(db, system, field, etype, control_id, captured=None, supersedes=None):
    data = EvidenceCreate(control_id=control_id, field=field, source="AGENTWATCH",
                          evidence_type=etype, captured_at=captured or datetime.now(timezone.utc),
                          payload={"x": 1}, supersedes=supersedes)
    return ingest_evidence(db, org_id=system.org_id, system_id=system.id, actor_id="tester", data=data)


def _controls_by_id(report):
    return {c["control_id"]: c for sec in report["sections"] for c in sec["controls"]}


def test_report_requires_assessment(clean, db):
    _loaded(db)
    system = _system(db)
    with pytest.raises(NoAssessment):
        build_annex_iv(db, org_id=system.org_id, system_id=system.id)


def test_report_traces_evidence_with_hashes(clean, db):
    _loaded(db)
    system = _system(db)
    ev = _ingest(db, system, "decision_trace", "telemetry_trace", "LOG_001")  # satisfies LOG_001
    run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")

    report = build_annex_iv(db, org_id=system.org_id, system_id=system.id)

    assert report["applicability"] == "APPLICABLE"
    assert report["watermark"] == "DRAFT"            # nothing is LEGAL_APPROVED yet
    assert report["note"] is None
    assert len(report["sections"]) == 9              # Annex IV sections 1..9
    assert report["assessment_timestamp"] is not None
    assert report["catalog_version"]

    controls = _controls_by_id(report)

    # LOG_001 feeds section 2; it is SATISFIED, hash-stamped, and traces the exact item.
    log = controls["LOG_001"]
    assert log["status"] == "SATISFIED"
    assert log["control_hash"]
    assert log["review_status"] in {"UNREVIEWED", "NEEDS_LEGAL_REVIEW"}
    assert len(log["evidence"]) >= 1
    item = log["evidence"][0]
    assert item["id"] == ev.id
    assert item["hash"] == ev.hash
    assert item["evidence_type"] == "telemetry_trace"
    assert item["trust_score"] == ev.trust_score

    # A control with no evidence is still present, MISSING, with empty evidence.
    other = next(c for c in controls.values() if c["status"] == "MISSING")
    assert other["evidence"] == []


def test_report_not_applicable(clean, db):
    _loaded(db)
    system = _system(db, tier="LIMITED")
    run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")

    report = build_annex_iv(db, org_id=system.org_id, system_id=system.id)

    assert report["applicability"] == "NOT_APPLICABLE"
    assert report["sections"] == []
    assert report["system_score"] is None
    assert report["watermark"] == "DRAFT"
    assert report["note"]


def test_report_endpoint_404_and_readonly(clean, db):
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(systems_router.router)
    app.include_router(assessments_router.router)
    client = TestClient(app)

    tok = client.post("/auth/register", json={
        "organization_name": "Acme", "email": "a@acme.test", "password": "supersecret1", "name": "A"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}
    sid = client.post("/systems", headers=headers, json={"name": "S"}).json()["id"]

    r = client.get(f"/systems/{sid}/report", headers=headers)
    assert r.status_code == 404                                              # no assessment yet
    assert db.query(AuditEvent).filter_by(action=ASSESSMENT_RUN).count() == 0  # GET emitted nothing
