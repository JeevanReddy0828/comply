#!/usr/bin/env python
"""Comply — scripted pilot journey (demo-script-first).

Proves the backend supports the full Week 3 user outcome end-to-end, BEFORE any
React is written. If this journey is painful here, no UI will save it.

    register org+admin
      -> create a HIGH-risk system
      -> run assessment           (LOG_001 is MISSING — no evidence yet)
      -> add one telemetry trace  (field=decision_trace, trust 90)
      -> re-run assessment        (LOG_001 flips MISSING -> SATISFIED)

Run against a live backend (default http://localhost:8000):

    python scripts/demo_journey.py
    BASE_URL=http://localhost:8000 python scripts/demo_journey.py

Exit code 0 = the money-shot worked. Non-zero = the journey is broken.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
DEMO_CONTROL = "LOG_001"  # Decision Trace Retention — requires TELEMETRY/decision_trace


def _print_step(n: int, title: str) -> None:
    print(f"\n\033[1m[{n}] {title}\033[0m")


def _status_line(results: list[dict]) -> str:
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())) or "(none)"


def _find(results: list[dict], control_id: str) -> dict | None:
    return next((r for r in results if r["control_id"] == control_id), None)


def main() -> int:
    # A fresh email every run so the script is idempotent against a persistent DB.
    stamp = int(time.time())
    email = f"pilot+{stamp}@example.com"
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    _print_step(1, "Register organization + admin")
    r = client.post(
        "/auth/register",
        json={
            "organization_name": "Northwind HR",
            "email": email,
            "password": "demo-pass-1234",
            "name": "Pilot Admin",
        },
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    print(f"    registered {email}; role={r.json()['user']['role']}")

    _print_step(2, "Register a HIGH-risk AI system")
    r = client.post(
        "/systems",
        json={
            "name": "Resume Screener",
            "intended_purpose": "Rank job applicants for recruiter review.",
            "deployment_context": "production",
            # Manual until the classifier lands. HIGH is what makes controls apply.
            "risk_tier": "HIGH",
            "annex_iii_category": "employment",
        },
    )
    r.raise_for_status()
    system_id = r.json()["id"]
    print(f"    system {system_id} (risk_tier=HIGH)")

    _print_step(3, "Run assessment - expect gaps (no evidence yet)")
    r = client.post(f"/assessments/run/{system_id}")
    r.raise_for_status()
    before = r.json()
    print(f"    applicability={before['applicability']} score={before['system_score']}")
    print(f"    counts: {before['counts']}")
    print(f"    controls: {_status_line(before['results'])}")
    before_log = _find(before["results"], DEMO_CONTROL)
    if before_log is None:
        print(f"    FAIL: {DEMO_CONTROL} not in applicable controls", file=sys.stderr)
        return 1
    print(f"    {DEMO_CONTROL} status: {before_log['status']} (score {before_log['score']})")
    if before_log["missing_requirements"]:
        miss = before_log["missing_requirements"][0]
        print(f"      missing: field={miss['field']} type={miss['type']} reason={miss['reason']}")

    _print_step(4, "Add evidence - a signed decision trace")
    r = client.post(
        f"/systems/{system_id}/evidence",
        json={
            "control_id": DEMO_CONTROL,
            "field": "decision_trace",
            "source": "AGENTWATCH",
            "evidence_type": "telemetry_trace",  # category TELEMETRY, trust 90
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"trace_id": "demo-001", "events": 42},
        },
    )
    r.raise_for_status()
    ev = r.json()
    print(f"    evidence {ev['id']} trust_score={ev['trust_score']} validity={ev['validity_state']}")

    _print_step(5, "Re-run assessment - expect LOG_001 satisfied")
    r = client.post(f"/assessments/run/{system_id}")
    r.raise_for_status()
    after = r.json()
    print(f"    score: {before['system_score']} -> {after['system_score']}")
    print(f"    counts: {after['counts']}")
    after_log = _find(after["results"], DEMO_CONTROL)
    print(f"    {DEMO_CONTROL} status: {before_log['status']} -> {after_log['status']}")

    ok = before_log["status"] == "MISSING" and after_log["status"] == "SATISFIED"
    print()
    if ok:
        print("\033[32m[OK] JOURNEY PASSED - control moved MISSING -> SATISFIED.\033[0m")
        return 0
    print("\033[31m[FAIL] JOURNEY BROKEN - control did not flip as expected.\033[0m", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP {e.response.status_code} on {e.request.method} {e.request.url}", file=sys.stderr)
        print(e.response.text, file=sys.stderr)
        sys.exit(2)
    except httpx.ConnectError:
        print(f"\nCould not reach backend at {BASE_URL}. Is it running?", file=sys.stderr)
        sys.exit(3)
