"""System lifecycle: atomic create + audit, org-scoped reads, tenant isolation."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit_actions import SYSTEM_CREATED
from app.models import AuditEvent, User
from app.routers import auth as auth_router
from app.routers import systems as systems_router
from app.services.audit import verify_chain
from app.services.auth import capabilities_for_role, create_access_token, hash_password


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(systems_router.router)
    return TestClient(app)


def _register(client, org, email):
    r = client.post("/auth/register", json={
        "organization_name": org, "email": email, "password": "supersecret1", "name": "Admin"})
    assert r.status_code == 201
    return r.json()["access_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_create_system_atomic_and_audited(clean, db):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")

    r = client.post("/systems", headers=_auth(tok), json={
        "name": "Resume Screener", "intended_purpose": "rank candidates",
        "deployment_context": "automated_decision", "risk_tier": "HIGH"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Resume Screener"
    # structured classification placeholder (not raw input)
    assert body["classification"] == {"risk_tier": "HIGH", "method": "manual_input", "confidence": 0.5}

    # audit event emitted, chain clean
    ev = db.query(AuditEvent).filter(AuditEvent.entity_id == body["id"]).one()
    assert ev.action == SYSTEM_CREATED
    assert verify_chain(db)["intact"] is True


def test_classification_defaults_when_tier_absent(clean):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    r = client.post("/systems", headers=_auth(tok), json={"name": "Chatbot"})
    assert r.json()["classification"]["risk_tier"] == "LIMITED"


def test_list_returns_only_org_systems(clean):
    client = _app()
    tok_a = _register(client, "OrgA", "a@a.test")
    tok_b = _register(client, "OrgB", "b@b.test")

    client.post("/systems", headers=_auth(tok_a), json={"name": "A-sys"})

    list_a = client.get("/systems", headers=_auth(tok_a)).json()
    list_b = client.get("/systems", headers=_auth(tok_b)).json()
    assert [s["name"] for s in list_a] == ["A-sys"]
    assert list_b == []


def test_cross_org_access_returns_404(clean):
    client = _app()
    tok_a = _register(client, "OrgA", "a@a.test")
    tok_b = _register(client, "OrgB", "b@b.test")

    sys_id = client.post("/systems", headers=_auth(tok_a), json={"name": "A-sys"}).json()["id"]

    assert client.get(f"/systems/{sys_id}", headers=_auth(tok_a)).status_code == 200
    assert client.get(f"/systems/{sys_id}", headers=_auth(tok_b)).status_code == 404


def test_readonly_cannot_create_system(clean, db):
    client = _app()
    _register(client, "Acme", "admin@acme.test")
    org_id = db.query(User).filter(User.email == "admin@acme.test").one().org_id

    reader = User(org_id=org_id, email="r@acme.test", password_hash=hash_password("supersecret1"),
                  name="R", role="ReadOnly", capabilities=capabilities_for_role("ReadOnly"), is_active=True)
    db.add(reader)
    db.commit()
    db.refresh(reader)

    r = client.post("/systems", headers=_auth(create_access_token(reader)), json={"name": "X"})
    assert r.status_code == 403
