"""Study session routes.

Group-scoped for creating and listing, flat for acting on one session —
the same split as tasks, so the group is always derived from the resource
rather than trusted from the URL.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.schemas.common import Paginated
from app.schemas.study_session import (
    MySessionResponse,
    RsvpRequest,
    SessionAttendee,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
)
from app.services.study_session import session_service

group_sessions_router = APIRouter()
sessions_router = APIRouter()


@group_sessions_router.post(
    "/{group_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    group_id: UUID,
    payload: SessionCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> SessionResponse:
    return await session_service.create_session(
        session, group_id=group_id, actor=current_user, payload=payload
    )


@group_sessions_router.get("/{group_id}/sessions", response_model=Paginated[SessionResponse])
async def list_sessions(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    pagination: Pagination,
    upcoming: Annotated[bool, Query()] = False,
    starts_after: Annotated[datetime | None, Query()] = None,
    starts_before: Annotated[datetime | None, Query()] = None,
) -> Paginated[SessionResponse]:
    """`upcoming=true` for the agenda; `starts_after`/`starts_before` for a
    calendar month, which needs past days of the current month too."""
    limit, offset = pagination
    return await session_service.list_sessions(
        session,
        group_id=group_id,
        actor=current_user,
        upcoming_only=upcoming,
        starts_after=starts_after,
        starts_before=starts_before,
        limit=limit,
        offset=offset,
    )


@sessions_router.get("/mine", response_model=list[MySessionResponse])
async def list_my_sessions(
    current_user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[MySessionResponse]:
    """Upcoming sessions across all of the caller's groups, for the dashboard."""
    return await session_service.list_my_sessions(session, actor=current_user, limit=limit)


@sessions_router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> SessionResponse:
    return await session_service.get_session(session, session_id=session_id, actor=current_user)


@sessions_router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    payload: SessionUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> SessionResponse:
    return await session_service.update_session(
        session, session_id=session_id, actor=current_user, payload=payload
    )


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await session_service.delete_session(session, session_id=session_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@sessions_router.put("/{session_id}/rsvp", response_model=SessionResponse)
async def set_rsvp(
    session_id: UUID,
    payload: RsvpRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> SessionResponse:
    """PUT, not POST: answering is idempotent and replaces any previous answer."""
    return await session_service.set_rsvp(
        session, session_id=session_id, actor=current_user, status=payload.status
    )


@sessions_router.delete("/{session_id}/rsvp", response_model=SessionResponse)
async def clear_rsvp(
    session_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> SessionResponse:
    return await session_service.clear_rsvp(
        session, session_id=session_id, actor=current_user
    )


@sessions_router.get("/{session_id}/rsvps", response_model=list[SessionAttendee])
async def list_attendees(
    session_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[SessionAttendee]:
    return await session_service.list_attendees(
        session, session_id=session_id, actor=current_user
    )
