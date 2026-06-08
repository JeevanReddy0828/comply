"""Remediation tasks: the operational layer that turns a control gap into owned,
trackable work. Pattern (invariant #4/#5): validate -> write -> append_event ->
commit, all in the caller's transaction; tenancy via scoped_get.

Tasks are mutable (status/owner/due evolve), but every transition emits a
hash-chained audit event, so a task's lifecycle is itself audit evidence."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit_actions import (
    ENTITY_TASK,
    TASK_CREATED,
    TASK_RESOLVED,
    TASK_UPDATED,
)
from app.models import AISystem, Assessment, AssessmentResult, Control, RemediationTask, User
from app.schemas.remediation import TaskCreate, TaskUpdate
from app.services.audit import append_event
from app.services.tenancy import scoped_get

_OPEN_STATES = ("OPEN", "IN_PROGRESS")


class RemediationError(Exception):
    pass


class SystemNotFound(RemediationError):
    pass


class TaskNotFound(RemediationError):
    pass


class OwnerNotFound(RemediationError):
    pass


class UnknownControl(RemediationError):
    pass


class DuplicateOpenTask(RemediationError):
    pass


def _validate_owner(db: Session, org_id: str, owner_id: str | None) -> None:
    if owner_id is None:
        return
    owner = scoped_get(db, User, org_id, owner_id)
    if owner is None:
        raise OwnerNotFound("Owner is not a user in this organization")


def _gap_reason_for(db: Session, org_id: str, system_id: str, control_id: str) -> str | None:
    """The reason this control was a gap at the latest assessment, frozen onto the
    task so its origin survives later state changes. NO_EVIDENCE | BELOW_MIN_SCORE |
    STALE, or None if there's no gap / no assessment yet."""
    latest = (
        db.query(Assessment)
        .filter(Assessment.system_id == system_id, Assessment.org_id == org_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if latest is None:
        return None
    result = (
        db.query(AssessmentResult)
        .filter(AssessmentResult.assessment_id == latest.id, AssessmentResult.control_id == control_id)
        .first()
    )
    if result is None or not result.missing_requirements:
        return None
    first = result.missing_requirements[0]
    reason = first.get("reason")
    if reason == "INSUFFICIENT":
        return first.get("detail")  # BELOW_MIN_SCORE | STALE
    return reason  # NO_EVIDENCE


def create_task(db: Session, *, org_id: str, system_id: str, actor_id: str, data: TaskCreate) -> RemediationTask:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        raise SystemNotFound("System not found")

    current = (
        db.query(Control)
        .filter(Control.control_id == data.control_id, Control.is_current.is_(True))
        .first()
    )
    if current is None:
        raise UnknownControl(f"Unknown control: {data.control_id}")

    _validate_owner(db, org_id, data.owner_id)

    task = RemediationTask(
        org_id=org_id,
        system_id=system_id,
        control_id=data.control_id,
        status="OPEN",
        owner_id=data.owner_id,
        due_date=data.due_date,
        notes=data.notes,
        source_gap_reason=_gap_reason_for(db, org_id, system_id, data.control_id),
        created_by=actor_id,
    )
    try:
        db.add(task)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateOpenTask(f"An open task already exists for {data.control_id}")

    try:
        append_event(
            db,
            actor=actor_id,
            action=TASK_CREATED,
            entity_type=ENTITY_TASK,
            entity_id=task.id,
            payload={
                "system_id": system_id,
                "control_id": data.control_id,
                "owner_id": data.owner_id,
                "source_gap_reason": task.source_gap_reason,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task


def update_task(db: Session, *, org_id: str, task_id: str, actor_id: str, data: TaskUpdate) -> RemediationTask:
    task = scoped_get(db, RemediationTask, org_id, task_id)
    if task is None:
        raise TaskNotFound("Task not found")

    fields = data.model_dump(exclude_unset=True)
    if "owner_id" in fields:
        _validate_owner(db, org_id, fields["owner_id"])

    resolving = False
    if "status" in fields and fields["status"] != task.status:
        new_status = fields["status"]
        if new_status == "RESOLVED":
            task.resolved_at = datetime.now(timezone.utc)
            task.resolved_by = actor_id
            task.resolution = "MANUAL"
            resolving = True
        else:
            # reopening clears resolution provenance
            task.resolved_at = None
            task.resolved_by = None
            task.resolution = None

    for key, value in fields.items():
        setattr(task, key, value)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateOpenTask(f"An open task already exists for {task.control_id}")

    try:
        append_event(
            db,
            actor=actor_id,
            action=TASK_RESOLVED if resolving else TASK_UPDATED,
            entity_type=ENTITY_TASK,
            entity_id=task.id,
            payload={"control_id": task.control_id, "changes": fields,
                     "resolution": task.resolution} if resolving
            else {"control_id": task.control_id, "changes": fields},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task


def list_tasks(db: Session, *, org_id: str, system_id: str | None = None) -> list[RemediationTask]:
    q = db.query(RemediationTask).filter(RemediationTask.org_id == org_id)
    if system_id is not None:
        q = q.filter(RemediationTask.system_id == system_id)
    return q.order_by(RemediationTask.created_at.desc()).all()


def get_task(db: Session, *, org_id: str, task_id: str) -> RemediationTask | None:
    return scoped_get(db, RemediationTask, org_id, task_id)


def auto_resolve_for_assessment(
    db: Session, *, org_id: str, system_id: str, satisfied_control_ids: set[str], actor: str = "system"
) -> list[str]:
    """Resolve open tasks whose control is now SATISFIED. Flush-only — runs inside
    the assessment's transaction so closures are atomic with the run and emit their
    own TASK_RESOLVED events. Terminal-state guard: only OPEN/IN_PROGRESS tasks are
    touched; already-RESOLVED tasks are never reopened or re-resolved."""
    if not satisfied_control_ids:
        return []
    tasks = (
        db.query(RemediationTask)
        .filter(
            RemediationTask.org_id == org_id,
            RemediationTask.system_id == system_id,
            RemediationTask.status.in_(_OPEN_STATES),
            RemediationTask.control_id.in_(satisfied_control_ids),
        )
        .all()
    )
    resolved: list[str] = []
    now = datetime.now(timezone.utc)
    for task in tasks:
        task.status = "RESOLVED"
        task.resolved_at = now
        task.resolved_by = actor
        task.resolution = "AUTO_SATISFIED"
        db.flush()
        append_event(
            db,
            actor=actor,
            action=TASK_RESOLVED,
            entity_type=ENTITY_TASK,
            entity_id=task.id,
            payload={"control_id": task.control_id, "resolution": "AUTO_SATISFIED",
                     "system_id": system_id},
        )
        resolved.append(task.id)
    return resolved
