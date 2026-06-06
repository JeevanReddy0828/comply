"""Combine the regex layer and the ML classifier into one verdict.

Decision policy:
- block  if any severity-3 rule matches, OR injection_probability >= block_threshold
- flag   if any lower-severity rule matches, OR injection_probability >= flag_threshold
- allow  otherwise
risk_score is the strongest signal seen (rule severity or model probability), 0-100."""
from __future__ import annotations

from app.config import settings
from app.guard import classifier, rules
from app.guard.schemas import GuardReason, GuardVerdict

_SEVERITY_SCORE = {1: 40, 2: 70, 3: 95}


def evaluate(text: str) -> GuardVerdict:
    hits = rules.scan(text)
    prob = classifier.injection_probability(text)  # None if unavailable

    reasons: list[GuardReason] = [
        GuardReason(source="rule", detail=f"{h.name}: '{h.snippet}'", severity=h.severity) for h in hits
    ]
    if prob is not None:
        reasons.append(GuardReason(source="model", detail="prompt-injection classifier", score=round(prob, 4)))

    max_sev = max((h.severity for h in hits), default=0)
    model_block = prob is not None and prob >= settings.guard_block_threshold
    model_flag = prob is not None and prob >= settings.guard_flag_threshold

    if max_sev >= 3 or model_block:
        action = "block"
    elif hits or model_flag:
        action = "flag"
    else:
        action = "allow"

    rule_score = _SEVERITY_SCORE.get(max_sev, 0)
    model_score = int((prob or 0.0) * 100)
    risk_score = max(rule_score, model_score)

    return GuardVerdict(
        action=action,
        blocked=action == "block",
        risk_score=risk_score,
        injection_probability=round(prob, 4) if prob is not None else None,
        classifier_available=prob is not None,
        reasons=reasons,
    )
