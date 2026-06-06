"""AI system lifecycle. Enforces the business-operation boundary: validate → DB
writes → append_event → commit, all in one transaction. Routers call these; they
never touch ORM models directly (keeps audit + tenancy un-bypassable)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit_actions import ENTITY_AI_SYSTEM, SYSTEM_CREATED
from app.models import AISystem
from app.schemas.system import SystemCreate
from app.services.audit import append_event
from app.services.tenancy import scoped_get


def create_system(db: Session, *, org_id: str, actor_id: str, data: SystemCreate) -> AISystem:
    resolved_tier = data.risk_tier or "LIMITED"
    classification = {
        "risk_tier": resolved_tier,
        "method": "manual_input",
        "confidence": 0.5,
    }
    system = AISystem(
        org_id=org_id,
        name=data.name,
        intended_purpose=data.intended_purpose,
        deployment_context=data.deployment_context,
        risk_tier=resolved_tier,
        annex_iii_category=data.annex_iii_category,
        classification=classification,
    )
    try:
        db.add(system)
        db.flush()
        append_event(
            db,
            actor=actor_id,
            action=SYSTEM_CREATED,
            entity_type=ENTITY_AI_SYSTEM,
            entity_id=system.id,
            payload={"name": system.name, "risk_tier": resolved_tier,
                     "annex_iii_category": data.annex_iii_category},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(system)
    return system


def list_systems(db: Session, *, org_id: str) -> list[AISystem]:
    return (
        db.query(AISystem)
        .filter(AISystem.org_id == org_id)
        .order_by(AISystem.created_at.desc())
        .all()
    )


def get_system(db: Session, *, org_id: str, system_id: str) -> AISystem | None:
    return scoped_get(db, AISystem, org_id, system_id)
