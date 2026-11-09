from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.services import token_store

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_ACCESS = "access"
_REFRESH = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _sign(claims: dict) -> str:
    return jwt.encode(
        claims, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": now, "jti": uuid4().hex, "type": _ACCESS})
    return _sign(to_encode)


def create_refresh_token(user_id: int | str) -> str:
    """Long-lived, single-use-per-rotation refresh token."""
    now = datetime.now(UTC)
    return _sign(
        {
            "sub": str(user_id),
            "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": now,
            "jti": uuid4().hex,
            "type": _REFRESH,
        }
    )


def decode_token(token: str, expected_type: str | None = _ACCESS) -> dict:
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
        )
    except jwt.PyJWTError as err:
        raise HTTPException(status_code=401, detail="Invalid token") from err

    token_type = claims.get("type", _ACCESS)
    if expected_type is not None and token_type != expected_type:
        raise HTTPException(status_code=401, detail="Invalid token type")

    jti = claims.get("jti")
    if jti and token_store.is_revoked(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return claims


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
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


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return (
            db.query(User)
            .filter(User.id == int(user_id), User.is_active.is_(True))
            .first()
        )
    except Exception:
        return None


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user
