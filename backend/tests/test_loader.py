"""Catalog loader: loads real catalog, is idempotent, versions instead of mutating."""
from pathlib import Path

import pytest
from sqlalchemy import func

from app.models import Control, ControlRequirement, EvidenceRequirement, Framework, Requirement
from app.services.loader import CatalogIntegrityError, load_catalog

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")


def test_loads_real_catalog(clean_graph):
    db = clean_graph
    summary = load_catalog(db, CATALOG)
    db.commit()

    assert summary["frameworks"] == 1
    assert summary["requirements"] == 10
    assert summary["controls_inserted"] == 30
    assert summary["controls_skipped"] == 0

    assert db.query(func.count(Framework.id)).scalar() == 1
    assert db.query(func.count(Requirement.id)).scalar() == 10
    assert db.query(func.count(Control.control_id)).scalar() == 30
    # every loaded control is the current version
    assert db.query(func.count()).select_from(Control).filter(Control.is_current.is_(True)).scalar() == 30


def test_idempotent(clean_graph):
    db = clean_graph
    load_catalog(db, CATALOG)
    db.commit()
    counts_1 = (
        db.query(func.count(Control.control_id)).scalar(),
        db.query(func.count(EvidenceRequirement.id)).scalar(),
        db.query(func.count(ControlRequirement.id)).scalar(),
    )

    summary = load_catalog(db, CATALOG)
    db.commit()
    counts_2 = (
        db.query(func.count(Control.control_id)).scalar(),
        db.query(func.count(EvidenceRequirement.id)).scalar(),
        db.query(func.count(ControlRequirement.id)).scalar(),
    )

    assert summary["controls_inserted"] == 0
    assert summary["controls_skipped"] == 30
    assert counts_1 == counts_2  # no duplication, identical state


def test_evidence_requirements_parsed(clean_graph):
    db = clean_graph
    load_catalog(db, CATALOG)
    db.commit()

    # LOG_001: telemetry decision_trace, 7d freshness, min_score 90
    er = (
        db.query(EvidenceRequirement)
        .filter_by(control_id="LOG_001", field="decision_trace")
        .one()
    )
    assert er.type == "TELEMETRY"
    assert er.freshness_seconds == 7 * 86400
    assert er.min_score == 90
    assert er.required is True


def test_control_requirements_linked(clean_graph):
    db = clean_graph
    load_catalog(db, CATALOG)
    db.commit()

    links = db.query(ControlRequirement).filter_by(control_id="LOG_001").all()
    assert {l.requirement_id for l in links} == {"TRACEABILITY"}


def test_backfills_null_control_hash_on_reload(clean_graph):
    db = clean_graph
    load_catalog(db, CATALOG)
    db.commit()

    # Simulate rows inserted before migration 0006 added control_hash.
    from sqlalchemy import update

    db.execute(update(Control).values(control_hash=None))
    db.commit()
    assert db.query(func.count()).select_from(Control).filter(Control.control_hash.is_(None)).scalar() == 30

    summary = load_catalog(db, CATALOG)
    db.commit()

    assert summary["controls_rehashed"] == 30          # content unchanged, hash backfilled
    assert summary["controls_inserted"] == 0
    assert summary["controls_skipped"] == 0
    assert db.query(func.count()).select_from(Control).filter(Control.control_hash.is_(None)).scalar() == 0

    # Idempotent: a subsequent reload now finds the hash set and plain-skips.
    again = load_catalog(db, CATALOG)
    db.commit()
    assert again["controls_rehashed"] == 0
    assert again["controls_skipped"] == 30


def test_drift_without_version_bump_raises(clean_graph):
    db = clean_graph
    load_catalog(db, CATALOG)
    db.commit()

    # Mutate a control file's content in-memory by feeding a tampered dict through
    # the same path: simulate by editing the DB row's source — instead, re-run the
    # loader with a monkeypatched read is overkill; assert the guard directly.
    ctrl = db.get(Control, ("LOG_001", 1))
    assert ctrl is not None
    from app.services import loader as loader_mod

    tampered = {
        "control_id": "LOG_001",
        "version": 1,                      # same version
        "name": "TAMPERED NAME",           # changed content
        "description": ctrl.description,
        "confidence": ctrl.confidence,
        "review_status": ctrl.review_status,
        "frameworks": ctrl.frameworks,
        "article_refs": ctrl.article_refs,
        "annex_refs": ctrl.annex_refs,
        "evidence_requirements": [],
        "requirements": [],
    }
    with pytest.raises(CatalogIntegrityError):
        loader_mod._load_control(db, tampered, "0.1.0")
