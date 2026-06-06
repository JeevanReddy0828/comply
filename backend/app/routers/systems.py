from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.system import SystemCreate, SystemOut
from app.security import require_capability
from app.services import systems as svc
from app.services.auth import CAN_MANAGE_SYSTEMS, CAN_VIEW_COMPLIANCE

router = APIRouter(prefix="/systems", tags=["systems"])


@router.post("", response_model=SystemOut, status_code=status.HTTP_201_CREATED)
def create_system(
    body: SystemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_MANAGE_SYSTEMS)),
):
    system = svc.create_system(db, org_id=user.org_id, actor_id=user.id, data=body)
    return SystemOut.model_validate(system)


@router.get("", response_model=list[SystemOut])
def list_systems(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    return [SystemOut.model_validate(s) for s in svc.list_systems(db, org_id=user.org_id)]


@router.get("/{system_id}", response_model=SystemOut)
def get_system(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    system = svc.get_system(db, org_id=user.org_id, system_id=system_id)
    if system is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    return SystemOut.model_validate(system)
