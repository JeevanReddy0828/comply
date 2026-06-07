"""Build the retrieval corpus from two sources:
- the EU AI Act consolidated text (data/eu_ai_act.txt), segmented by Article/Annex
- the Comply control catalog (compliance/*.yaml), one chunk per control/requirement
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.config import settings
from app.rag.chunker import Chunk, chunk_act

log = logging.getLogger("rag.corpus")


def _act_chunks() -> list[Chunk]:
    path = Path(settings.act_text_path)
    if not path.exists():
        log.warning("act text not found at %s — skipping", path)
        return []
    return chunk_act(path.read_text(encoding="utf-8"))


def _catalog_chunks() -> list[Chunk]:
    base = Path(settings.catalog_dir)
    chunks: list[Chunk] = []

    controls_dir = base / "controls" / "eu_ai_act"
    for f in sorted(controls_dir.glob("*.yaml")) if controls_dir.exists() else []:
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        cid = d.get("control_id", f.stem)
        parts = [f"Control {cid}: {d.get('name', '')}".strip(), (d.get("description") or "").strip()]
        ers = d.get("evidence_requirements") or []
        if ers:
            parts.append(
                "Evidence required: "
                + "; ".join(
                    f"{er.get('type')} '{er.get('field')}' (min_score {er.get('min_score')})" for er in ers
                )
            )
        refs = (d.get("article_refs") or []) + (d.get("annex_refs") or [])
        if refs:
            parts.append("References: " + ", ".join(map(str, refs)))
        chunks.append(Chunk(text="\n".join(p for p in parts if p), citation=f"Control {cid}", source="catalog"))

    reqs_dir = base / "requirements" / "eu_ai_act"
    for f in sorted(reqs_dir.glob("*.yaml")) if reqs_dir.exists() else []:
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rid = d.get("id", f.stem)
        parts = [f"Requirement {rid}: {d.get('name', '')}".strip(), (d.get("description") or "").strip()]
        refs = d.get("article_refs") or []
        if refs:
            parts.append("References: " + ", ".join(map(str, refs)))
        chunks.append(Chunk(text="\n".join(p for p in parts if p), citation=f"Requirement {rid}", source="catalog"))

    return chunks


def load_corpus() -> list[Chunk]:
    act = _act_chunks()
    catalog = _catalog_chunks()
    log.info("corpus: %d act chunks + %d catalog chunks", len(act), len(catalog))
    return act + catalog
