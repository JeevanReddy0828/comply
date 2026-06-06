"""Read-only catalog access. The catalog is global regulatory reference data
(not tenant-scoped). Only current control versions are exposed."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Control, ControlRequirement, Framework, Requirement


def list_frameworks(db: Session) -> list[Framework]:
    return db.query(Framework).order_by(Framework.id).all()


def list_requirements(db: Session, framework: str | None = None) -> list[Requirement]:
    q = db.query(Requirement)
    if framework:
        q = q.filter(Requirement.framework_id == framework)
    return q.order_by(Requirement.id).all()


def control_requirement_ids(db: Session, control_id: str, version: int) -> list[str]:
    rows = (
        db.query(ControlRequirement)
        .filter(ControlRequirement.control_id == control_id, ControlRequirement.control_version == version)
        .all()
    )
    return sorted(cr.requirement_id for cr in rows)


def list_controls(db: Session, framework: str | None = None, requirement: str | None = None) -> list[Control]:
    controls = (
        db.query(Control).filter(Control.is_current.is_(True)).order_by(Control.control_id).all()
    )
    if framework:
        controls = [c for c in controls if framework in (c.frameworks or [])]
    if requirement:
        linked = {
            cr.control_id
            for cr in db.query(ControlRequirement).filter(ControlRequirement.requirement_id == requirement).all()
        }
        controls = [c for c in controls if c.control_id in linked]
    return controls


def get_control(db: Session, control_id: str) -> Control | None:
    return (
        db.query(Control)
        .filter(Control.control_id == control_id, Control.is_current.is_(True))
        .first()
    )
