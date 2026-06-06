"""Fast, deterministic regex layer. Catches the obvious, well-known
prompt-injection / jailbreak phrasings before (and independently of) the ML
classifier — so the guard still works if the model isn't loaded."""
from __future__ import annotations

import re
from dataclasses import dataclass

# (name, severity 1-3, pattern). Severity 3 = strong block signal.
_RAW_RULES: list[tuple[str, int, str]] = [
    ("ignore_previous_instructions", 3, r"ignore\s+(all\s+)?(the\s+)?(previous|above|prior|earlier)\s+(instructions|prompts?|messages?|context)"),
    ("disregard_instructions", 3, r"disregard\s+(all\s+)?(the\s+)?(previous|above|prior|your)\s+(instructions|rules|prompts?)"),
    ("forget_instructions", 2, r"forget\s+(everything|all|what)\s+(you|i)\s+(were|was|have been|told)"),
    ("reveal_system_prompt", 3, r"(reveal|show|print|repeat|tell\s+me|what\s+(is|are))\s+(your|the)\s+(system\s+)?(prompt|instructions|rules|directives)"),
    ("override_rules", 2, r"(override|bypass|ignore)\s+(your|the|all)\s+(safety|content|guard)?\s*(rules|filters?|guidelines|restrictions)"),
    ("role_override", 2, r"you\s+are\s+now\s+(a|an|the)\b"),
    ("pretend_roleplay", 1, r"\b(pretend|act\s+as|roleplay|role-play)\s+(to\s+be\s+|as\s+|you('| a)re\s+)?"),
    ("dan_jailbreak", 3, r"\b(DAN|do\s+anything\s+now|developer\s+mode|jailbreak)\b"),
    ("system_tag_injection", 3, r"(<\|?\s*(system|im_start|endoftext)\s*\|?>|\[/?(INST|SYS)\])"),
    ("exfiltrate_secrets", 2, r"(print|reveal|leak|exfiltrate|send)\s+(the\s+)?(api[\s_-]?key|secret|password|token|credentials)"),
    ("no_restrictions", 2, r"(without|with\s+no|ignoring)\s+(any\s+)?(restrictions|limitations|filters?|rules|ethics)"),
]


@dataclass(frozen=True)
class RuleHit:
    name: str
    severity: int
    snippet: str


_COMPILED: list[tuple[str, int, re.Pattern[str]]] = [
    (name, sev, re.compile(pat, re.IGNORECASE)) for name, sev, pat in _RAW_RULES
]


def scan(text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for name, severity, pattern in _COMPILED:
        m = pattern.search(text)
        if m:
            hits.append(RuleHit(name=name, severity=severity, snippet=m.group(0)[:120]))
    return hits
