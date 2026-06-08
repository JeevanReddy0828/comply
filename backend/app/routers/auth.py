from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, OrganizationOut, RegisterRequest, TokenOut, UserOut
from app.security import get_current_user, require_capability
from app.services.auth import (
    CAN_VIEW_COMPLIANCE,
    authenticate,
    count_org_members,
    create_access_token,
    get_organization,
    list_org_users,
    register_org_and_admin,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_org_and_admin(db, body.organization_name, body.email, body.password, body.name)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(CAN_VIEW_COMPLIANCE)),
):
    """Org-scoped user list for the remediation owner picker."""
    return [UserOut.model_validate(u) for u in list_org_users(db, user.org_id)]


@router.get("/organization", response_model=OrganizationOut)
def organization(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The current user's organization (profile page)."""
    org = get_organization(db, user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationOut(
        id=org.id,
        name=org.name,
        created_at=org.created_at,
        member_count=count_org_members(db, user.org_id),
    )
