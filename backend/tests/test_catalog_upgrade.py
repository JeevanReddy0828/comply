"""Catalog evolution: old assessments stay pinned to the control versions they
evaluated; new assessments use the new versions."""
from pathlib import Path

from app.models import AISystem, AssessmentResult, Control, Organization
from app.services.assessment import run_assessment
from app.services.loader import load_catalog, _load_control

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")

LOG_001_V2 = {
    "control_id": "LOG_001",
    "version": 2,
    "name": "Decision Trace Retention (v2)",
    "description": "Updated wording for v2.",
    "confidence": "HIGH",
    "review_status": "UNREVIEWED",
    "frameworks": ["EU_AI_ACT"],
    "requirements": ["TRACEABILITY"],
    "article_refs": ["Art.12", "Art.19"],
    "annex_refs": ["Annex IV Section 2"],
    "evidence_requirements": [
        {"type": "TELEMETRY", "field": "decision_trace", "freshness": "7d",
         "min_score": 90, "required": True},
    ],
}


def _high_system(db):
    org = Organization(name="Acme")
    db.add(org)
    db.flush()
    s = AISystem(org_id=org.id, name="S", intended_purpose="x",
                 deployment_context="automated_decision", risk_tier="HIGH",
                 classification={"risk_tier": "HIGH", "method": "manual_input", "confidence": 0.5})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_assessment_pins_control_version_across_upgrade(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    system = _high_system(db)

    # Assessment 1 under catalog v1
    a1 = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    v1_row = db.query(AssessmentResult).filter_by(assessment_id=a1.id, control_id="LOG_001").one()
    assert v1_row.control_version == 1

    # Upgrade LOG_001 to version 2 (loader inserts new version, demotes old)
    _load_control(db, LOG_001_V2, "0.2.0")
    db.commit()
    versions = {(c.version, c.is_current) for c in db.query(Control).filter_by(control_id="LOG_001").all()}
    assert versions == {(1, False), (2, True)}

    # Assessment 2 under catalog v2
    a2 = run_assessment(db, org_id=system.org_id, system_id=system.id, actor_id="tester")
    v2_row = db.query(AssessmentResult).filter_by(assessment_id=a2.id, control_id="LOG_001").one()
    assert v2_row.control_version == 2

    # Assessment 1's result is unchanged — still pinned to v1
    v1_again = db.query(AssessmentResult).filter_by(assessment_id=a1.id, control_id="LOG_001").one()
    assert v1_again.control_version == 1
