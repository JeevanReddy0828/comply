"""Assessment engine: deterministic evaluation per the ratified v1 spec."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit_actions import ASSESSMENT_RUN
from app.models import AISystem, AuditEvent, AssessmentResult, Organization
from app.routers import assessments as assessments_router
from app.routers import auth as auth_router
from app.routers import systems as systems_router
from app.schemas.evidence import EvidenceCreate
from app.services.assessment import evaluate, run_assessment, summarize
from app.services.audit import verify_chain
from app.services.evidence import ingest_evidence
from app.services.loader import load_catalog

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")


def _loaded(db):
    load_catalog(db, CATALOG)
    db.commit()


def _system(db, tier="HIGH"):
    org = Organization(name="Acme")
    db.add(org)
    db.flush()
    s = AISystem(org_id=org.id, name="S", intended_purpose="x",
                 deployment_context="automated_decision", risk_tier=tier,
                 classification={"risk_tier": tier, "method": "manual_input", "confidence": 0.5})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _ingest(db, system, field, etype, captured=None, supersedes=None, control_id="LOG_001"):
    data = EvidenceCreate(control_id=control_id, field=field, source="AGENTWATCH",
                          evidence_type=etype, captured_at=captured or datetime.now(timezone.utc),
                          payload={"x": 1}, supersedes=supersedes)
    return ingest_evidence(db, org_id=system.org_id, system_id=system.id, actor_id="tester", data=data)


def _by_control(results):
    return {r.control_id: r for r in results}


def test_row_per_applicable_control_all_missing(clean, db):
    _loaded(db)
    system = _system(db)
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    results = db.query(AssessmentResult).filter_by(assessment_id=a.id).all()

    assert len(results) == 30  # a row for EVERY applicable control, even MISSING
    assert all(r.status == "MISSING" for r in results)
    assert all(r.score == 0 for r in results)
    assert all(r.freshness_grade is None for r in results)  # null, never 'D', for MISSING
    log = _by_control(results)["LOG_001"]
    assert log.missing_requirements[0]["reason"] == "NO_EVIDENCE"

    ev = db.query(AuditEvent).filter(AuditEvent.entity_id == a.id).one()
    assert ev.action == ASSESSMENT_RUN
    assert verify_chain(db)["intact"] is True


def test_satisfied_control(clean, db):
    _loaded(db)
    system = _system(db)
    _ingest(db, system, "decision_trace", "telemetry_trace")  # trust 90, TELEMETRY, fresh
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    log = _by_control(db.query(AssessmentResult).filter_by(assessment_id=a.id).all())["LOG_001"]
    assert log.status == "SATISFIED"
    assert log.score == 100
    assert log.freshness_grade == "A"
    assert log.evidence_count >= 1


def test_not_applicable_limited_system(clean, db):
    _loaded(db)
    system = _system(db, tier="LIMITED")
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    results = db.query(AssessmentResult).filter_by(assessment_id=a.id).all()
    assert results == []
    assert summarize(results)["applicability"] == "NOT_APPLICABLE"
    assert summarize(results)["system_score"] is None


def test_strict_match_field_and_category(clean, db):
    _loaded(db)
    system = _system(db)
    # right field, wrong category (DOCUMENT not TELEMETRY)
    _ingest(db, system, "decision_trace", "manual_document")
    # right category, wrong field
    _ingest(db, system, "not_the_field", "telemetry_trace")
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    log = _by_control(db.query(AssessmentResult).filter_by(assessment_id=a.id).all())["LOG_001"]
    assert log.status == "MISSING"
    reasons = {m["reason"] for m in log.missing_requirements if m["field"] == "decision_trace"}
    assert reasons == {"NO_EVIDENCE"}


def test_degraded_within_long_window_qualifies(clean, db):
    _loaded(db)
    system = _system(db)
    # DOC_003: DOCUMENT / declaration_of_conformity, min_score 40, freshness 3650d.
    # manual_document (trust 40), 400 days old -> DEGRADED at ingestion but inside window.
    _ingest(db, system, "declaration_of_conformity", "manual_document",
            captured=datetime.now(timezone.utc) - timedelta(days=400), control_id="DOC_003")
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    doc = _by_control(db.query(AssessmentResult).filter_by(assessment_id=a.id).all())["DOC_003"]
    assert doc.status == "SATISFIED"                 # DEGRADED did not block
    assert any(w["warning"] == "DEGRADED" for w in doc.warnings)  # but flagged


def test_supersede_no_fallback(clean, db):
    _loaded(db)
    system = _system(db)
    strong = _ingest(db, system, "decision_trace", "telemetry_trace")  # trust 90, qualifies
    # supersede with a weaker item (otel_span trust 85 < min 90)
    _ingest(db, system, "decision_trace", "otel_span", supersedes=strong.id)
    a = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    log = _by_control(db.query(AssessmentResult).filter_by(assessment_id=a.id).all())["LOG_001"]
    assert log.status == "MISSING"  # no fallback to the superseded strong item
    m = [x for x in log.missing_requirements if x["field"] == "decision_trace"][0]
    assert m["reason"] == "INSUFFICIENT"
    assert m["detail"] == "BELOW_MIN_SCORE"


def test_historical_reproducibility(clean, db):
    _loaded(db)
    system = _system(db)
    strong = _ingest(db, system, "decision_trace", "telemetry_trace")
    a1 = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    ts1 = a1.created_at
    stored = {r.control_id: (r.status, r.score, r.control_version)
              for r in db.query(AssessmentResult).filter_by(assessment_id=a1.id).all()}
    assert stored["LOG_001"][0] == "SATISFIED"

    # after T1: supersede the qualifying evidence with a non-qualifying one
    _ingest(db, system, "decision_trace", "otel_span", supersedes=strong.id)

    # re-evaluate AS OF the stored timestamp -> must reproduce a1 exactly
    replay = {r["control_id"]: (r["status"], r["score"], r["control_version"])
              for r in evaluate(db, system, ts1)}
    assert replay == stored

    # and a fresh evaluation now genuinely differs (LOG_001 no longer satisfied)
    now_eval = {r["control_id"]: r["status"] for r in evaluate(db, system, datetime.now(timezone.utc))}
    assert now_eval["LOG_001"] == "MISSING"


def test_get_compliance_readonly_no_run(clean, db):
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

    r = client.get(f"/systems/{sid}/compliance", headers=headers)
    assert r.status_code == 404                          # no run yet
    assert db.query(AuditEvent).filter_by(action=ASSESSMENT_RUN).count() == 0  # GET emitted nothing
