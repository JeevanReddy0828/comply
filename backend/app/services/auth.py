"""Authentication & authorization primitives: capability model, scrypt hashing,
JWT, and org-centric registration."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, User

# ── Capabilities (first-class) ────────────────────────────────────────────────
CAN_MANAGE_USERS = "can_manage_users"
CAN_MANAGE_SYSTEMS = "can_manage_systems"
CAN_INGEST_EVIDENCE = "can_ingest_evidence"
CAN_RUN_ASSESSMENT = "can_run_assessment"
CAN_VIEW_COMPLIANCE = "can_view_compliance"
CAN_APPROVE_CONTROLS = "can_approve_controls"
CAN_MANAGE_REMEDIATION = "can_manage_remediation"

ALL_CAPABILITIES = [
    CAN_MANAGE_USERS,
    CAN_MANAGE_SYSTEMS,
    CAN_INGEST_EVIDENCE,
    CAN_RUN_ASSESSMENT,
    CAN_VIEW_COMPLIANCE,
    CAN_APPROVE_CONTROLS,
    CAN_MANAGE_REMEDIATION,
]

ROLE_CAPABILITIES: dict[str, list[str]] = {
    "Admin": list(ALL_CAPABILITIES),
    "ComplianceOfficer": [
        CAN_MANAGE_SYSTEMS,
        CAN_INGEST_EVIDENCE,
        CAN_RUN_ASSESSMENT,
        CAN_VIEW_COMPLIANCE,
        CAN_APPROVE_CONTROLS,
        CAN_MANAGE_REMEDIATION,
    ],
    "ReadOnly": [CAN_VIEW_COMPLIANCE],
}


def list_org_users(db: Session, org_id: str) -> list[User]:
    """All active users in an org — used to populate the task-owner picker."""
    return (
        db.query(User)
        .filter(User.org_id == org_id, User.is_active.is_(True))
        .order_by(User.name, User.email)
        .all()
    )


def get_organization(db: Session, org_id: str) -> Organization | None:
    return db.get(Organization, org_id)


def count_org_members(db: Session, org_id: str) -> int:
    return (
        db.query(func.count(User.id))
        .filter(User.org_id == org_id, User.is_active.is_(True))
        .scalar()
    )


def capabilities_for_role(role: str) -> list[str]:
    return list(ROLE_CAPABILITIES.get(role, []))


# ── Password hashing (stdlib scrypt; params stored for future migration) ──────
_N, _R, _P = 16384, 8, 1


def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(plain.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${key.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        key = hashlib.scrypt(
            plain.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except (ValueError, AttributeError):
        return False


# ── JWT (access token only) ───────────────────────────────────────────────────
def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "org_id": user.org_id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expiration_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ── Registration & authentication ─────────────────────────────────────────────
def register_org_and_admin(db: Session, org_name: str, email: str, password: str, name: str) -> User:
    """Atomically create an organization and its first user (Admin)."""
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email already registered")

    org = Organization(name=org_name)
    db.add(org)
    db.flush()  # need org.id

    user = User(
        org_id=org.id,
        email=email,
        password_hash=hash_password(password),
        name=name,
        role="Admin",
        capabilities=capabilities_for_role("Admin"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
