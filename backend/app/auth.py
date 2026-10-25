from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


def has_permission(user: User, db=None, permission_name: str = None) -> bool:
    """Check whether a user holds a permission (by name 'resource:action' or resource/action pair).

    Superadmins always pass. Otherwise checks role->permission links and legacy JSONB grants.
    """
    if getattr(user, "role", None) == "superadmin":
        return True
    perms = get_user_permissions(user, db)
    if permission_name is None:
        return len(perms) > 0
    return permission_name in perms


def get_user_permissions(user: User, db) -> list:
    """Return the effective list of permission names for a user.

    Combines explicit RolePermission links with legacy Role.permissions JSONB lists.
    Safe when no roles are assigned (returns []).
    """
    names = set()
    try:
        user_roles = list(getattr(user, "roles", []) or [])
    except Exception:
        user_roles = []
    for ur in user_roles:
        role = getattr(ur, "role", None)
        if role is None:
            continue
        # Explicit join table
        for rp in list(getattr(role, "role_permissions", []) or []):
            perm = getattr(rp, "permission", None)
            if perm is not None and getattr(perm, "name", None):
                names.add(perm.name)
        # Legacy JSONB grant list
        legacy = getattr(role, "permissions", None)
        if isinstance(legacy, list):
            for item in legacy:
                if isinstance(item, str):
                    names.add(item)
                elif isinstance(item, dict) and item.get("name"):
                    names.add(item["name"])
    return sorted(names)

async def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    except Exception:
        return None

