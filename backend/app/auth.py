from datetime import datetime, timedelta
from typing import Optional
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import get_db
from app.models import User
from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

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
    """
    Dependency to require superadmin role.
    Only users with 'superadmin' role can pass this check.
    """
    if current_user.role != "superadmin":
        logger.warning(f"User {current_user.id} ({current_user.email}) attempted superadmin access without proper role")
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


def get_user_permissions(user: User, db: Session) -> list[str]:
    """
    Get all permission strings for a user based on their roles.
    Returns list of strings in format 'resource.action'.
    """
    permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(f"{perm.resource}.{perm.action}")
    return list(permissions)


def has_permission(user: User, resource: str, action: str, db: Session) -> bool:
    """
    Check if user has a specific permission through any of their roles.
    Superadmins always have all permissions.
    """
    if not user or not user.is_active:
        return False
    
    # Superadmin bypass - grant all permissions
    if user.role == "superadmin" or any(r.name == "superadmin" for r in user.roles):
        return True
    
    # Check all user roles for the permission
    for role in user.roles:
        for perm in role.permissions:
            if perm.resource == resource and perm.action == action:
                return True
    
    return False


async def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> Optional[User]:
    """
    Optional authentication dependency. Returns User if valid token provided, None otherwise.
    Does not raise exceptions for missing or invalid tokens - returns None silently.
    """
    if not token:
        return None
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            logger.debug("Token missing 'sub' claim")
            return None
        
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            logger.debug(f"Invalid user_id format in token: {user_id}")
            return None
        
        user = db.query(User).filter(
            User.id == user_id_int,
            User.is_active == True
        ).first()
        
        if user is None:
            logger.debug("User not found or inactive")
            return None
        
        return user
        
    except HTTPException:
        # decode_token raises HTTPException for invalid tokens
        logger.debug("Token decoding failed")
        return None
    except SQLAlchemyError as e:
        logger.error(f"Database error during optional auth: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during optional auth: {e}", exc_info=True)
        return None

