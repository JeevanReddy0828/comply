from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.assessment import AssessmentRunOut, ComplianceOut, ControlResultOut, GapsOut
from app.schemas.report import AnnexIVReport
from app.security import require_capability
from app.services import assessment as svc
from app.services import report as report_svc
from app.services.auth import CAN_RUN_ASSESSMENT, CAN_VIEW_COMPLIANCE

router = APIRouter(tags=["assessments"])


def _compliance_payload(assessment, results) -> dict:
    summary = svc.summarize(results)
    return {
        "system_id": assessment.system_id,
        "assessment_id": assessment.id,
        "assessment_timestamp": assessment.created_at,
        "catalog_version": assessment.catalog_version,
        "applicability": summary["applicability"],
        "system_score": summary["system_score"],
        "counts": summary["counts"],
        "results": [ControlResultOut.model_validate(r) for r in results],
    }


@router.post("/assessments/run/{system_id}", response_model=AssessmentRunOut,
             status_code=status.HTTP_201_CREATED)
def run(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_RUN_ASSESSMENT)),
):
    try:
        assessment = svc.run_assessment(db, org_id=user.org_id, system_id=system_id, actor_id=user.id)
    except svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    _, results = svc.get_latest_assessment(db, org_id=user.org_id, system_id=system_id)
    return _compliance_payload(assessment, results)


@router.get("/systems/{system_id}/compliance", response_model=ComplianceOut)
def compliance(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    try:
        assessment, results = svc.get_latest_assessment(db, org_id=user.org_id, system_id=system_id)
    except svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    except svc.NoAssessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No assessment yet; POST /assessments/run/{system_id}")
    return _compliance_payload(assessment, results)


@router.get("/systems/{system_id}/gaps", response_model=GapsOut)
def gaps(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    try:
        assessment, results = svc.get_latest_assessment(db, org_id=user.org_id, system_id=system_id)
    except svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    except svc.NoAssessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No assessment yet; POST /assessments/run/{system_id}")
    gaps = [ControlResultOut.model_validate(r) for r in results if r.status != "SATISFIED"]
    return {"system_id": system_id, "assessment_id": assessment.id, "gaps": gaps}


@router.get("/systems/{system_id}/report", response_model=AnnexIVReport)
def report(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    try:
        return report_svc.build_annex_iv(db, org_id=user.org_id, system_id=system_id)
    except report_svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    except report_svc.NoAssessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No assessment yet; POST /assessments/run/{system_id}")
