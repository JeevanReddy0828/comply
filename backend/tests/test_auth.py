"""Auth: authentication, capability authorization, and tenant isolation."""
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.models import AISystem, Organization, User
from app.security import get_current_user, require_capability
from app.services.auth import (
    CAN_MANAGE_SYSTEMS,
    capabilities_for_role,
    create_access_token,
    hash_password,
)
from app.services.tenancy import scoped_get
from app.routers import auth as auth_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    return TestClient(app)


def _register(client, org="Acme AI", email="admin@acme.test", pw="supersecret1"):
    return client.post(
        "/auth/register",
        json={"organization_name": org, "email": email, "password": pw, "name": "Admin"},
    )


# ── Authentication ────────────────────────────────────────────────────────────
def test_register_creates_org_and_admin(clean):
    client = _client()
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "Admin"
    assert set(body["user"]["capabilities"]) == set(capabilities_for_role("Admin"))
    assert body["access_token"]


def test_duplicate_email_rejected(clean):
    client = _client()
    _register(client)
    r = _register(client, org="Other")
    assert r.status_code == 400


def test_login_success_and_failure(clean):
    client = _client()
    _register(client)
    ok = client.post("/auth/login", json={"email": "admin@acme.test", "password": "supersecret1"})
    assert ok.status_code == 200
    bad = client.post("/auth/login", json={"email": "admin@acme.test", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_valid_token(clean):
    client = _client()
    token = _register(client).json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/auth/me").status_code == 401  # no creds → Unauthorized


def test_jwt_tampering_rejected(clean):
    client = _client()
    token = _register(client).json()["access_token"]
    # forge a new token with a different secret → signature invalid
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    forged = jwt.encode({**payload, "role": "Admin"}, "wrong-secret", algorithm="HS256")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_disabled_user_blocked(clean, db):
    client = _client()
    _register(client)
    token = client.post(
        "/auth/login", json={"email": "admin@acme.test", "password": "supersecret1"}
    ).json()["access_token"]

    user = db.query(User).filter(User.email == "admin@acme.test").first()
    user.is_active = False
    db.commit()

    # existing token now rejected
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    # and re-login blocked
    assert client.post(
        "/auth/login", json={"email": "admin@acme.test", "password": "supersecret1"}
    ).status_code == 401


# ── Capability authorization ──────────────────────────────────────────────────
def _probe_app() -> FastAPI:
    app = FastAPI()

    @app.post("/systems-probe")
    def create(_: User = Depends(require_capability(CAN_MANAGE_SYSTEMS))):
        return {"ok": True}

    return app


def _make_user(db, org_id, email, role):
    u = User(
        org_id=org_id, email=email, password_hash=hash_password("supersecret1"),
        name=role, role=role, capabilities=capabilities_for_role(role), is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_capability_enforced(clean, db):
    org = Organization(name="Acme")
    db.add(org)
    db.commit()
    admin = _make_user(db, org.id, "a@acme.test", "Admin")
    reader = _make_user(db, org.id, "r@acme.test", "ReadOnly")

    client = TestClient(_probe_app())
    admin_tok = create_access_token(admin)
    reader_tok = create_access_token(reader)

    assert client.post("/systems-probe", headers={"Authorization": f"Bearer {admin_tok}"}).status_code == 200
    assert client.post("/systems-probe", headers={"Authorization": f"Bearer {reader_tok}"}).status_code == 403


# ── Tenant isolation (service layer) ──────────────────────────────────────────
def test_org_isolation(clean, db):
    org_a = Organization(name="A")
    org_b = Organization(name="B")
    db.add_all([org_a, org_b])
    db.commit()

    sys_a = AISystem(org_id=org_a.id, name="A-system", intended_purpose="x", deployment_context="decision_support")
    db.add(sys_a)
    db.commit()

    # Same org → found
    assert scoped_get(db, AISystem, org_a.id, sys_a.id) is not None
    # Cross org → None (cannot reach another tenant's resource)
    assert scoped_get(db, AISystem, org_b.id, sys_a.id) is None
