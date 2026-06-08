"""Assessment engine. Deterministic evaluation over a frozen snapshot.

Spec (ratified v1):
- Frozen assessment_timestamp; candidate evidence = ingested_at <= timestamp.
- Applicable controls: current versions whose requirements' applies_to includes
  the system's risk_tier. Non-HIGH -> no applicable controls -> NOT_APPLICABLE.
- Eligible evidence = supersede-chain heads (no fallback).
- Match: exact field + category(evidence_type) == requirement.type.
- Qualify: trust_score >= min_score AND age <= control-specific freshness window.
- Requirement satisfied = >=1 qualifying item (binary OR). One item may satisfy
  many requirements.
- Control: all required satisfied -> SATISFIED; >=1 -> PARTIAL; none -> MISSING.
  score = round(satisfied/total*100). Equal weights.
- DEGRADED: informational warning only; the control window is the gate.
- A result row is persisted for EVERY applicable control (incl. MISSING).
- freshness_grade = null for MISSING (never 'D' there).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit_actions import ASSESSMENT_RUN, ENTITY_ASSESSMENT
from app.models import (
    AISystem,
    Assessment,
    AssessmentResult,
    Control,
    ControlRequirement,
    EvidenceItem,
    Framework,
    Requirement,
)
from app.services.audit import append_event
from app.services.evidence_registry import category_for
from app.services.tenancy import scoped_get

_GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


class AssessmentError(Exception):
    pass


class SystemNotFound(AssessmentError):
    pass


class NoAssessment(AssessmentError):
    pass


def _grade(age_seconds: float, window_seconds: int | None) -> str:
    if not window_seconds:
        return "A"
    r = age_seconds / window_seconds
    if r <= 0.25:
        return "A"
    if r <= 0.5:
        return "B"
    if r <= 1.0:
        return "C"
    return "D"


def _eligible_evidence(db: Session, org_id: str, system_id: str, as_of: datetime) -> list[EvidenceItem]:
    candidate = (
        db.query(EvidenceItem)
        .filter(
            EvidenceItem.system_id == system_id,
            EvidenceItem.org_id == org_id,
            EvidenceItem.ingested_at <= as_of,
        )
        .all()
    )
    superseded = {e.supersedes for e in candidate if e.supersedes}
    return [e for e in candidate if e.id not in superseded]


def _applicable_controls(db: Session, risk_tier: str | None) -> list[Control]:
    if not risk_tier:
        return []
    controls = db.query(Control).filter(Control.is_current.is_(True)).all()
    req_applies = {r.id: (r.applies_to or []) for r in db.query(Requirement).all()}
    links: dict[tuple[str, int], list[str]] = {}
    for cr in db.query(ControlRequirement).all():
        links.setdefault((cr.control_id, cr.control_version), []).append(cr.requirement_id)
    applicable = [
        c
        for c in controls
        if any(risk_tier in req_applies.get(rid, []) for rid in links.get((c.control_id, c.version), []))
    ]
    return sorted(applicable, key=lambda c: c.control_id)


def evaluate(db: Session, system: AISystem, as_of: datetime) -> list[dict]:
    """Pure evaluation — no writes. Returns one dict per applicable control."""
    eligible = _eligible_evidence(db, system.org_id, system.id, as_of)
    category = {e.id: category_for(e.evidence_type) for e in eligible}
    results = []

    for control in _applicable_controls(db, system.risk_tier):
        required = [er for er in control.evidence_requirements if er.required]
        scored = required or list(control.evidence_requirements)

        satisfied_count = 0
        missing: list[dict] = []
        warnings: list[dict] = []
        grades: list[str] = []
        qualifying_ids: set[str] = set()

        for er in scored:
            matching = [e for e in eligible if e.field == er.field and category.get(e.id) == er.type]
            if not matching:
                missing.append({"field": er.field, "type": er.type, "reason": "NO_EVIDENCE", "detail": None})
                continue

            def is_fresh(e: EvidenceItem) -> bool:
                if not er.freshness_seconds:
                    return True
                return (as_of - e.captured_at).total_seconds() <= er.freshness_seconds

            qualifying = [e for e in matching if e.trust_score >= er.min_score and is_fresh(e)]
            if qualifying:
                satisfied_count += 1
                rep = max(qualifying, key=lambda e: (e.trust_score, e.captured_at, e.ingested_at, e.id))
                qualifying_ids.update(e.id for e in qualifying)
                if er.freshness_seconds:
                    grades.append(_grade((as_of - rep.captured_at).total_seconds(), er.freshness_seconds))
                else:
                    grades.append("A")
                if rep.validity_state == "DEGRADED":
                    warnings.append({"field": er.field, "type": er.type, "warning": "DEGRADED"})
            else:
                has_score_ok = any(e.trust_score >= er.min_score for e in matching)
                detail = "STALE" if has_score_ok else "BELOW_MIN_SCORE"
                missing.append({"field": er.field, "type": er.type, "reason": "INSUFFICIENT", "detail": detail})

        total = len(scored)
        if satisfied_count == total:
            status = "SATISFIED"
        elif satisfied_count == 0:
            status = "MISSING"
        else:
            status = "PARTIAL"
        score = round(satisfied_count / total * 100) if total else 0
        grade = max(grades, key=lambda g: _GRADE_ORDER[g]) if (status != "MISSING" and grades) else None

        results.append(
            {
                "control_id": control.control_id,
                "control_version": control.version,
                "control_hash": control.control_hash,
                "status": status,
                "score": score,
                "freshness_grade": grade,
                "evidence_count": len(qualifying_ids),
                "evidence_ids": sorted(qualifying_ids),
                "missing_requirements": sorted(missing, key=lambda m: m["field"]),
                "warnings": sorted(warnings, key=lambda w: w["field"]),
            }
        )
    return results


def _active_catalog_version(db: Session) -> str:
    row = db.query(Framework.catalog_version).first()
    return row[0] if row else "unknown"


def run_assessment(db: Session, *, org_id: str, system_id: str, actor_id: str) -> Assessment:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        raise SystemNotFound("System not found")

    as_of = datetime.now(timezone.utc)
    evals = evaluate(db, system, as_of)
    catalog_version = _active_catalog_version(db)

    try:
        assessment = Assessment(
            system_id=system_id, org_id=org_id, catalog_version=catalog_version, created_at=as_of
        )
        db.add(assessment)
        db.flush()
        for r in evals:
            db.add(
                AssessmentResult(
                    assessment_id=assessment.id,
                    control_id=r["control_id"],
                    control_version=r["control_version"],
                    control_hash=r["control_hash"],
                    status=r["status"],
                    score=r["score"],
                    freshness_grade=r["freshness_grade"],
                    evidence_count=r["evidence_count"],
                    missing_requirements=r["missing_requirements"],
                    warnings=r["warnings"],
                )
            )
        append_event(
            db,
            actor=actor_id,
            action=ASSESSMENT_RUN,
            entity_type=ENTITY_ASSESSMENT,
            entity_id=assessment.id,
            payload={"system_id": system_id, "controls": len(evals), "catalog_version": catalog_version},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(assessment)
    return assessment


def get_latest_assessment(db: Session, *, org_id: str, system_id: str) -> tuple[Assessment, list[AssessmentResult]]:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        raise SystemNotFound("System not found")
    latest = (
        db.query(Assessment)
        .filter(Assessment.system_id == system_id, Assessment.org_id == org_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if latest is None:
        raise NoAssessment("No assessment yet")
    results = (
        db.query(AssessmentResult)
        .filter(AssessmentResult.assessment_id == latest.id)
        .order_by(AssessmentResult.control_id)
        .all()
    )
    return latest, results


def summarize(results: list[AssessmentResult]) -> dict:
    if not results:
        return {"applicability": "NOT_APPLICABLE", "system_score": None,
                "counts": {"SATISFIED": 0, "PARTIAL": 0, "MISSING": 0}}
    counts = {"SATISFIED": 0, "PARTIAL": 0, "MISSING": 0}
    for r in results:
        counts[r.status] += 1
    return {
        "applicability": "APPLICABLE",
        "system_score": round(sum(r.score for r in results) / len(results)),
        "counts": counts,
    }
