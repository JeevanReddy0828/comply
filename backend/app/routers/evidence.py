from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.evidence import EvidenceCreate, EvidenceOut
from app.security import require_capability
from app.services import evidence as svc
from app.services.auth import CAN_INGEST_EVIDENCE, CAN_VIEW_COMPLIANCE

router = APIRouter(prefix="/systems/{system_id}/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
def ingest(
    system_id: str,
    body: EvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_INGEST_EVIDENCE)),
):
    try:
        item = svc.ingest_evidence(db, org_id=user.org_id, system_id=system_id,
                                   actor_id=user.id, data=body)
    except svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    except (svc.UnknownEvidenceType, svc.InvalidCapturedAt, svc.InvalidSupersedes) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return EvidenceOut.model_validate(item)


@router.get("", response_model=list[EvidenceOut])
def list_evidence(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    items = svc.list_evidence(db, org_id=user.org_id, system_id=system_id)
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    return [EvidenceOut.model_validate(i) for i in items]
