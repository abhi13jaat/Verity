import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_token
from backend.db.models.user import User
from backend.db.postgres import get_db

_bearer = HTTPBearer(auto_error=False)

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTH
    try:
        payload = decode_token(creds.credentials)
        user_uuid = uuid.UUID(payload.get("sub", ""))
    except Exception:
        raise _UNAUTH
    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None or not user.is_active:
        raise _UNAUTH
    return user


async def get_current_user_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.id
