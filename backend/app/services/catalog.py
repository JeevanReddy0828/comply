"""Read-only catalog access. The catalog is global regulatory reference data
(not tenant-scoped). Only current control versions are exposed."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Control, ControlRequirement, Framework, Requirement


@lru_cache(maxsize=1)
def _article_index() -> dict[str, list[str]]:
    """Authoritative article -> control_ids map (article-level, e.g. 'Art.14'),
    from the version-controlled traceability index."""
    path = Path(settings.catalog_path) / "mappings" / "control_article_map.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(k): list(v) for k, v in (data.get("articles") or {}).items()}


def _article_num(article: str) -> int:
    m = re.search(r"(\d+)", article)
    return int(m.group(1)) if m else 0


def article_control_map(db: Session) -> list[tuple[str, list[Control]]]:
    """Each EU AI Act article -> its current feeding controls, ordered by article
    number. Articles with no resolvable current control are omitted."""
    current = {c.control_id: c for c in db.query(Control).filter(Control.is_current.is_(True)).all()}
    out: list[tuple[str, list[Control]]] = []
    for article, control_ids in _article_index().items():
        controls = [current[cid] for cid in control_ids if cid in current]
        if controls:
            out.append((article, sorted(controls, key=lambda c: c.control_id)))
    return sorted(out, key=lambda t: _article_num(t[0]))


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
