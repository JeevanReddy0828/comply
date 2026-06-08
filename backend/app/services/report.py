"""Annex IV technical-documentation assembler. Read-only: no writes, no audit
event (like GET /compliance).

The report is reconstructed by re-running the deterministic assessment at the
frozen assessment.created_at (invariant #8), so the statuses and the evidence
ids it traces are identical to the stored result — the document is self-proving.

Section -> control mapping is authoritative from compliance/mappings/
annex_iv_map.yaml; titles/fields/content_source labels come from
compliance/schemas/annex_iv_model.yaml (mirrors evidence_registry loading)."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AISystem, Control, EvidenceItem
from app.services.assessment import (
    NoAssessment,
    SystemNotFound,
    evaluate,
    get_latest_assessment,
    summarize,
)
from app.services.tenancy import scoped_get

__all__ = ["build_annex_iv", "SystemNotFound", "NoAssessment"]


@lru_cache(maxsize=1)
def _section_controls() -> dict[int, list[str]]:
    path = Path(settings.catalog_path) / "mappings" / "annex_iv_map.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {int(k): list(v) for k, v in (data.get("annex_iv_sections") or {}).items()}


@lru_cache(maxsize=1)
def _section_labels() -> dict[int, dict]:
    path = Path(settings.catalog_path) / "schemas" / "annex_iv_model.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {int(s["section"]): s for s in (data.get("sections") or [])}


def build_annex_iv(db: Session, *, org_id: str, system_id: str) -> dict:
    system = scoped_get(db, AISystem, org_id, system_id)
    if system is None:
        raise SystemNotFound("System not found")

    assessment, results = get_latest_assessment(db, org_id=org_id, system_id=system_id)
    summary = summarize(results)

    base = {
        "system": {
            "id": system.id,
            "name": system.name,
            "intended_purpose": system.intended_purpose,
            "deployment_context": system.deployment_context,
            "risk_tier": system.risk_tier,
            "annex_iii_category": system.annex_iii_category,
        },
        "applicability": summary["applicability"],
        "assessment_id": assessment.id,
        "assessment_timestamp": assessment.created_at,
        "catalog_version": assessment.catalog_version,
        "generated_at": datetime.now(timezone.utc),
        "system_score": summary["system_score"],
        "counts": summary["counts"],
    }

    if summary["applicability"] == "NOT_APPLICABLE":
        return {
            **base,
            "watermark": "DRAFT",
            "note": (
                "Annex IV technical documentation is not required: this system is "
                "not classified high-risk under the EU AI Act."
            ),
            "sections": [],
        }

    # Reconstruct at the frozen timestamp so evidence ids match the stored result.
    evals = {r["control_id"]: r for r in evaluate(db, system, assessment.created_at)}

    referenced = sorted({eid for r in evals.values() for eid in r["evidence_ids"]})
    evidence_by_id: dict[str, EvidenceItem] = {}
    if referenced:
        for e in (
            db.query(EvidenceItem)
            .filter(EvidenceItem.id.in_(referenced), EvidenceItem.org_id == org_id)
            .all()
        ):
            evidence_by_id[e.id] = e

    labels = _section_labels()
    sections: list[dict] = []
    review_statuses: list[str] = []

    for sec_num, control_ids in sorted(_section_controls().items()):
        meta = labels.get(sec_num, {})
        controls: list[dict] = []
        for cid in control_ids:
            r = evals.get(cid)
            if r is None:
                continue  # not applicable to this risk tier (or absent from catalog)
            ctrl = db.get(Control, (cid, r["control_version"]))
            review_status = ctrl.review_status if ctrl else "UNREVIEWED"
            review_statuses.append(review_status)
            evidence = [
                {
                    "id": evidence_by_id[eid].id,
                    "field": evidence_by_id[eid].field,
                    "evidence_type": evidence_by_id[eid].evidence_type,
                    "source": evidence_by_id[eid].source,
                    "trust_score": evidence_by_id[eid].trust_score,
                    "captured_at": evidence_by_id[eid].captured_at,
                    "hash": evidence_by_id[eid].hash,
                }
                for eid in r["evidence_ids"]
                if eid in evidence_by_id
            ]
            controls.append(
                {
                    "control_id": cid,
                    "control_version": r["control_version"],
                    "control_hash": r["control_hash"],
                    "name": ctrl.name if ctrl else cid,
                    "status": r["status"],
                    "score": r["score"],
                    "review_status": review_status,
                    "confidence": ctrl.confidence if ctrl else "LOW",
                    "missing_requirements": r["missing_requirements"],
                    "evidence": evidence,
                }
            )
        sections.append(
            {
                "section": sec_num,
                "title": meta.get("title", f"Section {sec_num}"),
                "content_source": meta.get("content_source"),
                "fields": list(meta.get("fields", [])),
                "controls": controls,
            }
        )

    watermark = (
        "LEGAL_APPROVED"
        if review_statuses and all(s == "LEGAL_APPROVED" for s in review_statuses)
        else "DRAFT"
    )
    return {**base, "watermark": watermark, "note": None, "sections": sections}
