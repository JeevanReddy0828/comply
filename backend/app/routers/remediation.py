from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.remediation import TaskCreate, TaskOut, TaskUpdate
from app.security import require_capability
from app.services import remediation as svc
from app.services.auth import CAN_MANAGE_REMEDIATION, CAN_VIEW_COMPLIANCE

router = APIRouter(tags=["remediation"])


@router.post("/systems/{system_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    system_id: str,
    body: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_MANAGE_REMEDIATION)),
):
    try:
        task = svc.create_task(db, org_id=user.org_id, system_id=system_id, actor_id=user.id, data=body)
    except svc.SystemNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    except svc.UnknownControl as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except svc.OwnerNotFound as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except svc.DuplicateOpenTask as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TaskOut.model_validate(task)


@router.get("/systems/{system_id}/tasks", response_model=list[TaskOut])
def list_system_tasks(
    system_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    return [TaskOut.model_validate(t) for t in svc.list_tasks(db, org_id=user.org_id, system_id=system_id)]


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    task = svc.get_task(db, org_id=user.org_id, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskOut.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_MANAGE_REMEDIATION)),
):
    try:
        task = svc.update_task(db, org_id=user.org_id, task_id=task_id, actor_id=user.id, data=body)
    except svc.TaskNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except svc.OwnerNotFound as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except svc.DuplicateOpenTask as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TaskOut.model_validate(task)
