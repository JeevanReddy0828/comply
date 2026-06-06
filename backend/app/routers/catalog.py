from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Control, User
from app.schemas.catalog import (
    ControlDetailOut,
    ControlSummaryOut,
    EvidenceRequirementOut,
    FrameworkOut,
    RequirementOut,
)
from app.security import get_current_user
from app.services import catalog as svc

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _summary(db: Session, c: Control) -> ControlSummaryOut:
    return ControlSummaryOut(
        control_id=c.control_id, version=c.version, name=c.name,
        confidence=c.confidence, review_status=c.review_status,
        frameworks=c.frameworks, article_refs=c.article_refs, annex_refs=c.annex_refs,
        requirements=svc.control_requirement_ids(db, c.control_id, c.version),
    )


@router.get("/frameworks", response_model=list[FrameworkOut])
def frameworks(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [FrameworkOut.model_validate(f) for f in svc.list_frameworks(db)]


@router.get("/requirements", response_model=list[RequirementOut])
def requirements(
    framework: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return [RequirementOut.model_validate(r) for r in svc.list_requirements(db, framework)]


@router.get("/controls", response_model=list[ControlSummaryOut])
def controls(
    framework: str | None = None,
    requirement: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return [_summary(db, c) for c in svc.list_controls(db, framework, requirement)]


@router.get("/controls/{control_id}", response_model=ControlDetailOut)
def control_detail(
    control_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    c = svc.get_control(db, control_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")
    summary = _summary(db, c)
    return ControlDetailOut(
        **summary.model_dump(),
        description=c.description,
        catalog_version=c.catalog_version,
        evidence_requirements=[EvidenceRequirementOut.model_validate(er) for er in c.evidence_requirements],
    )
