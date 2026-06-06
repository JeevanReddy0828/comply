"""Evidence ingestion: immutable, deterministic trust, lineage, isolation, audit."""
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit_actions import EVIDENCE_INGESTED, EVIDENCE_SUPERSEDED
from app.models import AuditEvent, EvidenceItem
from app.routers import auth as auth_router
from app.routers import evidence as evidence_router
from app.routers import systems as systems_router
from app.services.audit import verify_chain


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(systems_router.router)
    app.include_router(evidence_router.router)
    return TestClient(app)


def _register(client, org, email):
    return client.post("/auth/register", json={
        "organization_name": org, "email": email, "password": "supersecret1", "name": "A"}).json()["access_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _now_iso(delta=timedelta(0)):
    return (datetime.now(timezone.utc) + delta).isoformat()


def _make_system(client, tok, name="S"):
    return client.post("/systems", headers=_auth(tok), json={"name": name}).json()["id"]


def _evidence(control_id="LOG_001", evidence_type="telemetry_trace", captured=None, supersedes=None):
    return {
        "control_id": control_id, "field": "decision_trace", "source": "AGENTWATCH",
        "evidence_type": evidence_type, "captured_at": captured or _now_iso(),
        "payload": {"trace_id": "abc"}, "supersedes": supersedes,
    }


def test_ingest_stores_immutable_record(clean, db):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)

    r = client.post(f"/systems/{sid}/evidence", headers=_auth(tok), json=_evidence())
    assert r.status_code == 201
    body = r.json()
    assert body["trust_score"] == 90           # telemetry_trace from registry (deterministic)
    assert body["validity_state"] == "VALID"
    assert body["hash"]

    ev = db.query(AuditEvent).filter(AuditEvent.entity_id == body["id"]).one()
    assert ev.action == EVIDENCE_INGESTED
    assert verify_chain(db)["intact"] is True


def test_unknown_evidence_type_rejected(clean):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)
    r = client.post(f"/systems/{sid}/evidence", headers=_auth(tok),
                    json=_evidence(evidence_type="made_up_type"))
    assert r.status_code == 422


def test_future_captured_at_rejected(clean):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)
    r = client.post(f"/systems/{sid}/evidence", headers=_auth(tok),
                    json=_evidence(captured=_now_iso(timedelta(hours=1))))
    assert r.status_code == 422


def test_degraded_when_stale(clean):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)
    r = client.post(f"/systems/{sid}/evidence", headers=_auth(tok),
                    json=_evidence(captured=_now_iso(timedelta(days=-400))))
    assert r.status_code == 201
    assert r.json()["validity_state"] == "DEGRADED"


def test_supersede_inserts_new_leaves_old_unchanged(clean, db):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)

    first = client.post(f"/systems/{sid}/evidence", headers=_auth(tok), json=_evidence()).json()
    old_before = db.query(EvidenceItem).filter_by(id=first["id"]).one()
    old_snapshot = (old_before.validity_state, old_before.supersedes, old_before.trust_score, old_before.hash)

    second = client.post(f"/systems/{sid}/evidence", headers=_auth(tok),
                         json=_evidence(supersedes=first["id"])).json()

    # pure insert: two rows, new one points back, old one untouched
    assert db.query(EvidenceItem).count() == 2
    assert second["supersedes"] == first["id"]
    db.expire_all()
    old_after = db.query(EvidenceItem).filter_by(id=first["id"]).one()
    assert (old_after.validity_state, old_after.supersedes, old_after.trust_score, old_after.hash) == old_snapshot
    assert old_after.supersedes is None  # old row never gained a pointer

    ev = db.query(AuditEvent).filter(AuditEvent.entity_id == second["id"]).one()
    assert ev.action == EVIDENCE_SUPERSEDED


def test_lineage_retrievable(clean):
    client = _app()
    tok = _register(client, "Acme", "a@acme.test")
    sid = _make_system(client, tok)
    first = client.post(f"/systems/{sid}/evidence", headers=_auth(tok), json=_evidence()).json()
    second = client.post(f"/systems/{sid}/evidence", headers=_auth(tok),
                         json=_evidence(supersedes=first["id"])).json()

    items = client.get(f"/systems/{sid}/evidence", headers=_auth(tok)).json()
    by_id = {i["id"]: i for i in items}
    assert by_id[second["id"]]["supersedes"] == first["id"]
    assert by_id[first["id"]]["supersedes"] is None
    # current = items not superseded by any other
    superseded = {i["supersedes"] for i in items if i["supersedes"]}
    current = [i["id"] for i in items if i["id"] not in superseded]
    assert current == [second["id"]]


def test_cross_system_ingestion_blocked(clean):
    client = _app()
    tok_a = _register(client, "OrgA", "a@a.test")
    tok_b = _register(client, "OrgB", "b@b.test")
    sid_a = _make_system(client, tok_a)

    # B tries to ingest into A's system
    r = client.post(f"/systems/{sid_a}/evidence", headers=_auth(tok_b), json=_evidence())
    assert r.status_code == 404
    # B cannot list A's evidence either
    assert client.get(f"/systems/{sid_a}/evidence", headers=_auth(tok_b)).status_code == 404
