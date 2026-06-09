"""Catalog read API: authenticated, current-version, filterable."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth as auth_router
from app.routers import catalog as catalog_router
from app.services.loader import load_catalog

CATALOG = str(Path(__file__).resolve().parents[2] / "compliance")


def _client():
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(catalog_router.router)
    return TestClient(app)


def _token(client):
    return client.post("/auth/register", json={
        "organization_name": "Acme", "email": "a@acme.test", "password": "supersecret1", "name": "A"
    }).json()["access_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_requires_auth(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    assert client.get("/catalog/frameworks").status_code == 401


def test_frameworks(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    tok = _token(client)
    r = client.get("/catalog/frameworks", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == "EU_AI_ACT"


def test_requirements_and_filter(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    tok = _token(client)
    assert len(client.get("/catalog/requirements", headers=_auth(tok)).json()) == 10
    assert len(client.get("/catalog/requirements?framework=EU_AI_ACT", headers=_auth(tok)).json()) == 10
    assert client.get("/catalog/requirements?framework=NOPE", headers=_auth(tok)).json() == []


def test_controls_and_requirement_filter(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    tok = _token(client)
    assert len(client.get("/catalog/controls", headers=_auth(tok)).json()) == 30
    traceability = client.get("/catalog/controls?requirement=TRACEABILITY", headers=_auth(tok)).json()
    assert {c["control_id"] for c in traceability} == {"LOG_001", "LOG_002", "LOG_003", "LOG_004"}


def test_articles_to_controls(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    tok = _token(client)
    r = client.get("/catalog/articles", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    by_article = {a["article"]: [c["control_id"] for c in a["controls"]] for a in body}
    # Art.14 (human oversight) → the HUMAN controls
    assert by_article["Art.14"] == ["HUMAN_001", "HUMAN_002", "HUMAN_003", "HUMAN_004"]
    assert by_article["Art.12"] == ["LOG_001", "LOG_002", "LOG_003"]
    # ordered by article number
    nums = [int(a["article"].split(".")[1].split("(")[0]) for a in body]
    assert nums == sorted(nums)
    # control summaries carry review_status for the Ask panel
    assert all("review_status" in c for a in body for c in a["controls"])


def test_control_detail(clean, db):
    load_catalog(db, CATALOG)
    db.commit()
    client = _client()
    tok = _token(client)
    r = client.get("/catalog/controls/LOG_001", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["control_id"] == "LOG_001"
    assert body["version"] == 1
    assert body["confidence"] == "HIGH"
    assert body["requirements"] == ["TRACEABILITY"]
    er = body["evidence_requirements"]
    assert len(er) == 1
    assert er[0]["field"] == "decision_trace"
    assert er[0]["freshness_seconds"] == 7 * 86400
    assert er[0]["min_score"] == 90

    assert client.get("/catalog/controls/NOPE", headers=_auth(tok)).status_code == 404
