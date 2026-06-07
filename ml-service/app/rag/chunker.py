"""Split source documents into retrievable chunks with citation labels.

EU AI Act text is segmented at Article / Annex / Chapter headings (so each chunk
carries a real citation like "Article 6" or "Annex III"); long segments are
windowed. The catalog is chunked one document per control / requirement."""
from __future__ import annotations

import re
from dataclasses import dataclass

_MAX_CHARS = 1400
_OVERLAP = 200

# Heading boundaries in the consolidated Act text.
_HEADING = re.compile(r"(?m)^\s*(Article\s+\d+[a-z]?|ANNEX\s+[IVXLC]+|CHAPTER\s+[IVXLC]+)\b")


@dataclass
class Chunk:
    text: str
    citation: str
    source: str  # "eu_ai_act" | "catalog"


def _window(text: str, citation: str, source: str) -> list[Chunk]:
    text = text.strip()
    if len(text) <= _MAX_CHARS:
        return [Chunk(text=text, citation=citation, source=source)] if text else []
    out: list[Chunk] = []
    start = 0
    while start < len(text):
        end = min(start + _MAX_CHARS, len(text))
        out.append(Chunk(text=text[start:end].strip(), citation=citation, source=source))
        if end == len(text):
            break
        start = end - _OVERLAP
    return out


def chunk_act(text: str) -> list[Chunk]:
    matches = list(_HEADING.finditer(text))
    chunks: list[Chunk] = []
    # Preamble / recitals before the first heading.
    if matches and matches[0].start() > 0:
        chunks += _window(text[: matches[0].start()], "Preamble & Recitals", "eu_ai_act")
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        citation = re.sub(r"\s+", " ", m.group(1)).strip().title() if m.group(1)[0].isupper() else m.group(1)
        # Normalize: "ANNEX III" -> "Annex III", "Article 6" stays
        citation = m.group(1).replace("ANNEX", "Annex").replace("CHAPTER", "Chapter")
        chunks += _window(text[m.start():end], citation, "eu_ai_act")
    return [c for c in chunks if len(c.text) > 40]
