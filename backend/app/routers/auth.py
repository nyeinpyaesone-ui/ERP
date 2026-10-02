from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.database import get_db
from app.models import Role, User
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()

ALLOWED_ROLES = {"user", "admin"}  # superadmin only via require_superadmin


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None
    roles: list[str] | None = None  # Role names to assign


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create and return a user with the legacy ``user`` role.

    Assign the RBAC ``user`` role if it exists and commit the account. Raise
    HTTP 400 if the email already exists.
    """
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role="user",
    )
    db.add(user)
    db.flush()

    # Assign default "user" role from RBAC system
    user_role = db.query(Role).filter(Role.name == "user").first()
    if user_role:
        user.roles.append(user_role)

    db.commit()
    db.refresh(user)
    log_activity(
        db,
        user_id=user.id,
        action="user_registered",
        entity_type="user",
        entity_id=user.id,
    )
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Authenticate using an email in ``username`` and return a bearer token and user.

    Update and commit the last-login time. Raise HTTP 401 for invalid
    credentials or a disabled account.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role})
    log_activity(
        db, user_id=user.id, action="user_login", entity_type="user", entity_id=user.id
    )

    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read")),
):
    """Return users after skipping ``skip`` records, limited to ``limit`` records."""
    return db.query(User).offset(skip).limit(limit).all()


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update")),
):
    """Commit explicitly supplied fields and return the updated user.

    A non-null ``roles`` list replaces assigned RBAC roles; unknown names are
    ignored and an empty list removes all roles. Omitted or null ``roles``
    leaves assignments intact. Raise HTTP 404 if the user does not exist.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)
    roles = update_data.pop("roles", None)
    for key, value in update_data.items():
        if hasattr(user, key) and key not in ("id", "hashed_password", "role"):
            setattr(user, key, value)

    if roles is not None:
        # Sync roles - remove existing, add new
        user.roles.clear()
        for role_name in roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role:
                user.roles.append(role)

    db.commit()
    db.refresh(user)
    return user
