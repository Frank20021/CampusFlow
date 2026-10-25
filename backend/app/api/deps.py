from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
user_repository = UserRepository()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DbSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            code="not_authenticated",
            message="Authentication required",
            status_code=401,
        )
    user_id = decode_access_token(credentials.credentials)
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise AppError(
            code="not_authenticated",
            message="Authentication required",
            status_code=401,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_streaming_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID:
    """Authenticate without touching the database.

    `get_db` releases its connection only once the response is finished, and
    an SSE response is finished when the student closes the tab. Depending on
    `CurrentUser` here would therefore hold one pooled connection per open
    chat for as long as it stays open, and a handful of tabs would drain the
    pool for the whole API. Streaming routes decode the token here and take a
    short-lived session by hand for the membership check.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            code="not_authenticated",
            message="Authentication required",
            status_code=401,
        )
    return decode_access_token(credentials.credentials)


StreamingUserId = Annotated[UUID, Depends(get_streaming_user_id)]


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    return limit, offset


Pagination = Annotated[tuple[int, int], Depends(pagination_params)]


def parse_uuid(value: str, *, name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise AppError(
            code="invalid_id",
            message=f"Invalid {name}",
            status_code=400,
        ) from exc
