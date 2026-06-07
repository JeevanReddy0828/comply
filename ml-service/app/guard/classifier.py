"""DeBERTa prompt-injection classifier, lazily loaded and gracefully optional.

The heavy deps (torch/transformers) and the model download only happen on first
use. If they're unavailable, the guard degrades to the regex layer instead of
crashing — `available()` reports which mode is active."""
from __future__ import annotations

import logging
import threading

from app.config import settings

log = logging.getLogger("guard.classifier")

_pipe = None
_load_attempted = False
_load_error: str | None = None
_lock = threading.Lock()


def _load():
    global _pipe, _load_attempted, _load_error
    with _lock:
        if _load_attempted:
            return
        _load_attempted = True
        if not settings.enable_classifier:
            _load_error = "classifier disabled via config"
            return
        try:
            from transformers import pipeline  # heavy import, deferred

            _pipe = pipeline(
                "text-classification",
                model=settings.guard_model,
                top_k=None,  # return scores for all labels
                truncation=True,
                max_length=512,
            )
            log.info("loaded guard model %s", settings.guard_model)
        except Exception as e:  # torch/transformers missing, download failed, etc.
            _load_error = f"{type(e).__name__}: {e}"
            log.warning("guard classifier unavailable (%s) — falling back to rules", _load_error)


def available() -> bool:
    _load()
    return _pipe is not None


def status() -> dict:
    _load()
    return {
        "available": _pipe is not None,
        "model": settings.guard_model if _pipe is not None else None,
        "error": _load_error,
    }


def injection_probability(text: str) -> float | None:
    """P(injection) in [0,1], or None if the classifier is unavailable."""
    _load()
    if _pipe is None:
        return None
    results = _pipe(text)
    # top_k=None yields a list of [{label, score}, ...] (possibly nested per input)
    scores = results[0] if results and isinstance(results[0], list) else results
    label = settings.guard_injection_label.upper()
    for entry in scores:
        if str(entry["label"]).upper() == label:
            return float(entry["score"])
    return 0.0
