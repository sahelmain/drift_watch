from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ApiKey, User

_security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    scopes: dict | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    raw_key = f"dw_{secrets.token_urlsafe(32)}"
    key_hash = _hash_api_key(raw_key)
    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        name=name,
        org_id=org_id,
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    return api_key, raw_key


async def verify_api_key(db: AsyncSession, raw_key: str) -> ApiKey | None:
    key_hash = _hash_api_key(raw_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        return None
    api_key.last_used_at = datetime.now(UTC)
    await db.flush()
    return api_key


async def _resolve_user_from_token(
    token: str,
    db: AsyncSession,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Supports both JWT Bearer tokens and API keys (Bearer dw_...)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if token.startswith("dw_"):
        api_key = await verify_api_key(db, token)
        if api_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        result = await db.execute(
            select(User).where(User.org_id == api_key.org_id, User.role == "admin").limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No admin user for org")
        return user

    return await _resolve_user_from_token(token, db)


def require_role(*roles: str):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _checker
