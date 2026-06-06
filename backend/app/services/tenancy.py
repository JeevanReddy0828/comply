"""Tenant isolation enforced at the service layer. Every cross-tenant lookup goes
through scoped_get so org_id is a required input, not a router afterthought."""
from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


def scoped_get(db: Session, model: type[T], org_id: str, pk) -> T | None:
    """Return the row only if it exists AND belongs to org_id. Otherwise None.
    Models passed here must expose an `org_id` attribute."""
    obj = db.get(model, pk)
    if obj is None or getattr(obj, "org_id", None) != org_id:
        return None
    return obj
