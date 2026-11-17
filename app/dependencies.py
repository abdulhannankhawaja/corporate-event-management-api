"""Reusable FastAPI dependencies."""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.exceptions import UnauthorizedError
from app.models import User
from app.security import decode_access_token
from app.services import get_user_by_username

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
db_dependency = Depends(get_db)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = db_dependency,
) -> User:
    """Resolve the current user from an optional bearer token."""
    if token is None:
        raise UnauthorizedError("Not authenticated")
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise UnauthorizedError("Invalid or expired token")
    user = await get_user_by_username(db, username)
    if user is None:
        raise UnauthorizedError("Invalid or expired token")
    return user


@dataclass(frozen=True)
class Pagination:
    """Define validated pagination query parameters."""

    skip: int = 0
    limit: int = 10


def get_pagination(
    skip: Annotated[
        int,
        Query(ge=0, description="Number of records to skip."),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of records to return.",
        ),
    ] = 10,
) -> Pagination:
    """Build a pagination value from validated query parameters."""
    return Pagination(skip=skip, limit=limit)


PaginationDependency = Annotated[Pagination, Depends(get_pagination)]
