"""Deterministic evidence-type → trust_score lookup, loaded from the
version-controlled registry (compliance/schemas/evidence_types.yaml).

Trust is a fixed registry value — never ML, never runtime-variable — so
re-ingesting the same evidence yields the same score and compliance history
stays reproducible."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.config import settings


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict]:
    path = Path(settings.catalog_path) / "schemas" / "evidence_types.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("evidence_types", {})


def trust_score_for(evidence_type: str) -> int | None:
    """Fixed trust score, or None if the type is not in the registry."""
    entry = _registry().get(evidence_type)
    return None if entry is None else int(entry["trust_score"])


def category_for(evidence_type: str) -> str | None:
    entry = _registry().get(evidence_type)
    return None if entry is None else entry.get("category")


def known_types() -> list[str]:
    return sorted(_registry().keys())
