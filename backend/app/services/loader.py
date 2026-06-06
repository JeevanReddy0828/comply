"""Catalog loader. Reads version-controlled regulatory YAML (compliance/) into
the graph tables. The YAML is the source of truth; the DB is a queryable mirror.

Guarantees:
- Idempotent: loading the same catalog twice produces identical state.
- Versioned, not mutated: a control row is keyed (control_id, version). A version
  bump INSERTs a new row and demotes the prior `is_current`; existing versions are
  never edited.
- Drift-guarded: if a control file's content changed but its `version` did not,
  the load raises — enforcing the review-methodology rule that content changes
  must bump the version.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models import (
    Control,
    ControlRequirement,
    EvidenceRequirement,
    Framework,
    Requirement,
)
from app.services.audit import compute_payload_hash

_DURATION_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def _content_hash(data: dict, ev_reqs: list[dict], req_ids: list[str]) -> str:
    """sha256 of the control's canonicalized semantic content. Independent of YAML
    formatting/key order; excludes governance metadata (confidence/review_status)."""
    payload = {
        "control_id": data["control_id"],
        "version": int(data["version"]),
        "name": data["name"],
        "description": str(data["description"]).strip(),
        "article_refs": sorted(data.get("article_refs", [])),
        "annex_refs": sorted(data.get("annex_refs", [])),
        "requirements": sorted(req_ids),
        "evidence_requirements": sorted(
            [e["type"], e["field"], e["freshness_seconds"], e["min_score"], e["required"]]
            for e in ev_reqs
        ),
    }
    return compute_payload_hash(payload)


class CatalogIntegrityError(Exception):
    pass


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_duration(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = re.fullmatch(r"(\d+)([dhms])", str(value).strip())
    if not m:
        raise CatalogIntegrityError(f"Bad freshness duration: {value!r}")
    return int(m.group(1)) * _DURATION_UNITS[m.group(2)]


def _norm_evidence_reqs(data: dict) -> list[dict]:
    out = []
    for er in data.get("evidence_requirements", []):
        out.append(
            {
                "type": er["type"],
                "field": er["field"],
                "freshness_seconds": _parse_duration(er.get("freshness")),
                "min_score": int(er.get("min_score", 0)),
                "required": bool(er.get("required", True)),
            }
        )
    return out


def _control_differs(existing: Control, data: dict, ev_reqs: list[dict], req_ids: list[str]) -> bool:
    if (
        existing.name != data["name"]
        or existing.description.strip() != str(data["description"]).strip()
        or existing.confidence != data["confidence"]
        or existing.review_status != data["review_status"]
        or sorted(existing.frameworks) != sorted(data.get("frameworks", []))
        or sorted(existing.article_refs) != sorted(data.get("article_refs", []))
        or sorted(existing.annex_refs) != sorted(data.get("annex_refs", []))
    ):
        return True
    existing_ev = sorted(
        ((e.type, e.field, e.freshness_seconds, e.min_score, e.required) for e in existing.evidence_requirements)
    )
    new_ev = sorted((e["type"], e["field"], e["freshness_seconds"], e["min_score"], e["required"]) for e in ev_reqs)
    if existing_ev != new_ev:
        return True
    existing_reqs = sorted(cr.requirement_id for cr in _control_req_links(existing))
    if existing_reqs != sorted(req_ids):
        return True
    return False


def _control_req_links(control: Control) -> list[ControlRequirement]:
    # session-bound lazy query avoided; resolved by caller via object_session
    from sqlalchemy import inspect

    session = inspect(control).session
    return (
        session.query(ControlRequirement)
        .filter_by(control_id=control.control_id, control_version=control.version)
        .all()
    )


def _load_framework(db: Session, data: dict, catalog_version: str) -> None:
    fw = db.get(Framework, data["id"])
    fields = dict(
        name=data["name"],
        version=data["version"],
        jurisdiction=data["jurisdiction"],
        catalog_version=catalog_version,
        effective_date=str(data.get("effective_date")) if data.get("effective_date") else None,
        source_url=data.get("source_url"),
    )
    if fw:
        for k, v in fields.items():
            setattr(fw, k, v)
    else:
        db.add(Framework(id=data["id"], **fields))


def _load_requirement(db: Session, data: dict, framework_id: str, catalog_version: str) -> None:
    req = db.get(Requirement, data["id"])
    fields = dict(
        framework_id=framework_id,
        name=data["name"],
        description=str(data["description"]).strip(),
        article_refs=data.get("article_refs", []),
        applies_to=data.get("applies_to", []),
        catalog_version=catalog_version,
    )
    if req:
        for k, v in fields.items():
            setattr(req, k, v)
    else:
        db.add(Requirement(id=data["id"], **fields))


def _load_control(db: Session, data: dict, catalog_version: str) -> str:
    cid = data["control_id"]
    ver = int(data["version"])
    ev_reqs = _norm_evidence_reqs(data)
    req_ids = list(data.get("requirements", []))

    existing = db.get(Control, (cid, ver))
    if existing:
        if _control_differs(existing, data, ev_reqs, req_ids):
            raise CatalogIntegrityError(
                f"{cid} v{ver} content changed without a version bump "
                f"(review_methodology requires version bump on content change)"
            )
        return "skipped"

    for current in db.query(Control).filter(Control.control_id == cid, Control.is_current.is_(True)).all():
        current.is_current = False

    db.add(
        Control(
            control_id=cid,
            version=ver,
            name=data["name"],
            description=str(data["description"]).strip(),
            confidence=data["confidence"],
            review_status=data["review_status"],
            is_current=True,
            frameworks=data.get("frameworks", []),
            article_refs=data.get("article_refs", []),
            annex_refs=data.get("annex_refs", []),
            catalog_version=catalog_version,
            control_hash=_content_hash(data, ev_reqs, req_ids),
        )
    )
    for er in ev_reqs:
        db.add(EvidenceRequirement(control_id=cid, control_version=ver, **er))
    for rid in req_ids:
        db.add(ControlRequirement(control_id=cid, control_version=ver, requirement_id=rid))
    return "inserted"


def load_catalog(db: Session, catalog_dir: str | Path) -> dict:
    """Load all frameworks under catalog_dir into the graph. Returns a summary.
    Runs in the caller's transaction — commit/rollback is the caller's choice."""
    root = Path(catalog_dir)
    manifest = _read_yaml(root / "VERSION.yaml")
    catalog_version = manifest["catalog_version"]

    summary = {"catalog_version": catalog_version, "frameworks": 0, "requirements": 0,
               "controls_inserted": 0, "controls_skipped": 0}

    for fw_file in sorted((root / "frameworks").glob("*.yaml")):
        fw_data = _read_yaml(fw_file)
        slug = fw_file.stem
        _load_framework(db, fw_data, catalog_version)
        summary["frameworks"] += 1

        for req_file in sorted((root / "requirements" / slug).glob("*.yaml")):
            _load_requirement(db, _read_yaml(req_file), fw_data["id"], catalog_version)
            summary["requirements"] += 1

        db.flush()  # requirements must exist before control_requirements FK

        for ctrl_file in sorted((root / "controls" / slug).glob("*.yaml")):
            result = _load_control(db, _read_yaml(ctrl_file), catalog_version)
            summary[f"controls_{result}"] += 1

    return summary
