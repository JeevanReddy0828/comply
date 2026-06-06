#!/usr/bin/env python
"""Comply — realistic demo seed.

Stands up a believable HR-tech scenario for demos / dogfooding / landing-page
screenshots: a HIGH-risk "Resume Screener" that is *partly* compliant, so the
dashboard opens mid-range with a few sharp, explainable gaps — the way a real
customer's system actually looks (not an empty system slowly filling up).

The story it tells: the team has runtime monitoring, human oversight, risk
management, transparency and robustness handled; data governance is partial;
technical documentation, quality management, post-market monitoring and incident
reporting are the gaps.

It reads each control's *actual* evidence requirements from the catalog and
synthesizes qualifying evidence, so it stays correct as the catalog evolves.

    python scripts/seed_demo.py
    BASE_URL=... DEMO_EMAIL=... DEMO_PASSWORD=... python scripts/seed_demo.py

Re-runnable: registers the demo org once, then logs in on subsequent runs and
creates a fresh system each time.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
EMAIL = os.environ.get("DEMO_EMAIL", "demo@comply.dev")
PASSWORD = os.environ.get("DEMO_PASSWORD", "ComplyDemo123")

# Highest-trust evidence type per requirement category, with a sensible source.
# Mirrors compliance/schemas/evidence_types.yaml (static catalog content).
BEST_BY_CATEGORY = {
    "TELEMETRY": ("human_override_event", 95, "AGENTWATCH"),
    "ATTESTATION": ("incident_record", 80, "MANUAL"),
    "CONFIG": ("config_declaration", 70, "API"),
    "DOCUMENT": ("manual_document", 40, "MANUAL"),
}

# The believable HR-tech posture, by control-id prefix.
# Note: every control in the current catalog has a single evidence requirement,
# so the PARTIAL (amber) state is unreachable — a control is green or red. We
# therefore seed an honest green/red split rather than faking amber.
FULLY = {"LOG", "HUMAN", "RISK", "TRANS", "ROBUST", "DATA"}  # green — handled
# everything else (DOC, QMS, PMM, INC) → red — the gaps


def auth(client: httpx.Client) -> None:
    r = client.post(
        "/auth/register",
        json={"organization_name": "Northwind HR", "email": EMAIL, "password": PASSWORD, "name": "Demo Admin"},
    )
    if r.status_code == 400:  # already registered → log in
        r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"


def scored_requirements(detail: dict) -> list[dict]:
    """Mirror the engine: required reqs, or all if none are flagged required."""
    reqs = detail.get("evidence_requirements", [])
    required = [er for er in reqs if er.get("required")]
    return required or reqs


def make_evidence(control_id: str, er: dict) -> dict | None:
    best = BEST_BY_CATEGORY.get(er["type"])
    if not best:
        return None
    etype, trust, source = best
    if trust < er["min_score"]:  # can't satisfy this requirement's threshold
        return None
    return {
        "control_id": control_id,
        "field": er["field"],
        "source": source,
        "evidence_type": etype,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"seeded": True, "control": control_id, "field": er["field"]},
    }


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=20.0)
    auth(client)
    print(f"  authed as {EMAIL}")

    sys_resp = client.post(
        "/systems",
        json={
            "name": "Resume Screener",
            "intended_purpose": "Rank and shortlist job applicants for recruiter review.",
            "deployment_context": "production",
            "risk_tier": "HIGH",
            "annex_iii_category": "employment",
        },
    )
    sys_resp.raise_for_status()
    system_id = sys_resp.json()["id"]
    print(f"  created system {system_id}")

    controls = client.get("/catalog/controls").json()
    seeded = skipped = 0
    for summary in controls:
        cid = summary["control_id"]
        prefix = cid.split("_")[0]
        if prefix not in FULLY:
            continue  # leave as a gap

        detail = client.get(f"/catalog/controls/{cid}").json()
        for er in scored_requirements(detail):
            ev = make_evidence(cid, er)
            if ev is None:
                skipped += 1
                continue
            resp = client.post(f"/systems/{system_id}/evidence", json=ev)
            resp.raise_for_status()
            seeded += 1

    print(f"  seeded {seeded} evidence items ({skipped} requirements unsatisfiable, left as gaps)")

    result = client.post(f"/assessments/run/{system_id}").json()
    counts = result["counts"]
    by_status: dict[str, list[str]] = {"SATISFIED": [], "PARTIAL": [], "MISSING": []}
    for r in result["results"]:
        by_status[r["status"]].append(r["control_id"])

    print("\n" + "=" * 56)
    print(f"  Resume Screener — {result['system_score']}% compliant")
    print(f"  SATISFIED {counts['SATISFIED']}  PARTIAL {counts['PARTIAL']}  MISSING {counts['MISSING']}")
    print("=" * 56)
    for status in ("SATISFIED", "PARTIAL", "MISSING"):
        ids = by_status[status]
        if ids:
            print(f"  {status:9} {', '.join(ids)}")
    print("\n  Demo login : ", EMAIL, "/", PASSWORD)
    print(f"  Open       : {FRONTEND_URL}/systems/{system_id}")
    return 0


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
