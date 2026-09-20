from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import User, Role
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


def _ensure_default_role(db: Session, role_name: str, display_name: str, description: str = None) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is not None:
        return role

    role = Role(
        name=role_name,
        display_name=display_name,
        description=description or f"System role: {role_name}",
        is_system=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def ensure_user_roles(db: Session, user: User) -> User:
    if user is None:
        return user

    # Ensure the user has at least the default 'user' role in the RBAC tables.
    if user.roles is not None and len(user.roles) > 0:
        user_role_names = {role.name for role in user.roles}
    else:
        user_role_names = set()

    if "user" not in user_role_names:
        default_role = _ensure_default_role(db, "user", "Standard User", "Default portal access")
        if default_role not in user.roles:
            user.roles.append(default_role)

    # Keep compatibility with older code paths that still use `user.role`.
    if user.role not in {"user", "admin", "superadmin", None, ""}:
        user.role = "user"
    if not user.role:
        user.role = "user"

    if user.role == "admin" and "admin" not in user_role_names:
        admin_role = _ensure_default_role(db, "admin", "Administrator", "Administrative access")
        if admin_role not in user.roles:
            user.roles.append(admin_role)
    if user.role == "superadmin" and "superadmin" not in user_role_names:
        superadmin_role = _ensure_default_role(db, "superadmin", "Super Administrator", "Full system access")
        if superadmin_role not in user.roles:
            user.roles.append(superadmin_role)

    return user


def user_has_any_role(user: User, role_names: List[str]) -> bool:
    if not user:
        return False

    user_roles = {role.name for role in user.roles}
    if user.role and user.role.lower() in {name.lower() for name in role_names}:
        return True
    return bool(user_roles.intersection({name.lower() for name in role_names}))


def user_has_permission(user: User, permission_name: str, db: Session) -> bool:
    if not user:
        return False

    if user.role == "superadmin":
        return True

    permission_names = set()
    for role in user.roles:
        for perm in role.permissions:
            permission_names.add(f"{perm.resource}:{perm.action}")

    if permission_name in permission_names:
        return True

    # Backward compatibility for legacy strings.
    if user.role == "admin" and permission_name.startswith("admin:"):
        return True
    return False


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.id == int(user_id))
        .first()
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and user.tenant_id is not None:
        try:
            if int(token_tenant_id) != int(user.tenant_id):
                raise HTTPException(status_code=401, detail="Tenant mismatch")
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid tenant scope")

    user = ensure_user_roles(db, user)
    db.refresh(user)
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = ensure_user_roles(db, current_user)
    if not user_has_any_role(user, ["admin", "superadmin"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None

        user = (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.id == int(user_id), User.is_active == True)
            .first()
        )
        if user is None:
            return None

        token_tenant_id = payload.get("tenant_id")
        if token_tenant_id is not None and user.tenant_id is not None:
            try:
                if int(token_tenant_id) != int(user.tenant_id):
                    return None
            except (TypeError, ValueError):
                return None

        return ensure_user_roles(db, user)
    except Exception:
        return None


async def require_superadmin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = ensure_user_roles(db, current_user)
    if not user_has_any_role(user, ["superadmin"]):
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


async def has_permission(current_user: User, permission_name: str, db: Session) -> bool:
    if current_user is None:
        return False
    current_user = ensure_user_roles(db, current_user)
    if user_has_any_role(current_user, ["superadmin"]):
        return True
    return user_has_permission(current_user, permission_name, db)


async def get_user_permissions(user: User, db: Session) -> List[str]:
    if user is None:
        return []

    user = ensure_user_roles(db, user)
    if user_has_any_role(user, ["superadmin"]):
        return ["*"]

    permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(f"{perm.resource}:{perm.action}")

    if user.role == "admin":
        permissions.add("admin:access")
    return sorted(permissions)


__all__ = [
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "decode_token",
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_superadmin",
    "has_permission",
    "get_user_permissions",
    "ensure_user_roles",
    "user_has_any_role",
]
