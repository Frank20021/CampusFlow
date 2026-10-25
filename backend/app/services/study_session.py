"""Study session scheduling and RSVPs.

Permissions mirror tasks: any member can put a session on the group's
calendar, and only the person who created it (or an owner/admin, for
moderation) can change or remove it. Editing someone else's meeting time is
more disruptive than editing a task, so edits are narrower here than on the
board.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.membership import GroupMembership
from app.models.study_session import RsvpStatus, SessionRsvp, StudySession
from app.models.user import User
from app.repositories import (
    group_repository,
    membership_repository,
    session_repository,
)
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.study_session import SessionRepository
from app.schemas.common import Paginated
from app.schemas.study_session import (
    MySessionResponse,
    RsvpCounts,
    SessionAttendee,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
    SessionUser,
    validate_window,
)
from app.services.access import is_owner_or_admin, require_group_and_membership
from app.services.notification import notification_service


def _now() -> datetime:
    return datetime.now(UTC)


class SessionService:
    def __init__(
        self,
        sessions: SessionRepository | None = None,
        groups: GroupRepository | None = None,
        memberships: MembershipRepository | None = None,
    ) -> None:
        self.sessions = sessions or session_repository
        self.groups = groups or group_repository
        self.memberships = memberships or membership_repository

    async def create_session(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        payload: SessionCreateRequest,
    ) -> SessionResponse:
        group, membership = await self._membership(session, group_id, actor.id)

        study_session = StudySession(
            group_id=group_id,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            start_time=payload.start_time,
            end_time=payload.end_time,
            created_by=actor.id,
        )
        await self.sessions.add(session, study_session)

        # The creator is presumed to be attending; anything else would show a
        # brand new session with nobody going, including the organiser.
        await self.sessions.add_rsvp(
            session,
            SessionRsvp(
                session_id=study_session.id, user_id=actor.id, status=RsvpStatus.GOING
            ),
        )
        await notification_service.notify_session_created(
            session,
            actor=actor,
            group_id=group_id,
            group_name=group.name,
            session_id=study_session.id,
            session_title=study_session.title,
        )
        return await self._response_for(session, study_session.id, actor, membership)

    async def list_sessions(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        upcoming_only: bool,
        starts_after: datetime | None,
        starts_before: datetime | None,
        limit: int,
        offset: int,
    ) -> Paginated[SessionResponse]:
        _group, membership = await self._membership(session, group_id, actor.id)
        rows, total = await self.sessions.list_for_group(
            session,
            group_id=group_id,
            user_id=actor.id,
            upcoming_only=upcoming_only,
            starts_after=starts_after,
            starts_before=starts_before,
            now=_now(),
            limit=limit,
            offset=offset,
        )
        items = [_to_response(*row, actor=actor, membership=membership) for row in rows]
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def get_session(
        self, session: AsyncSession, *, session_id: UUID, actor: User
    ) -> SessionResponse:
        study_session, membership = await self._session_and_membership(session, session_id, actor)
        return await self._response_for(session, study_session.id, actor, membership)

    async def update_session(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        actor: User,
        payload: SessionUpdateRequest,
    ) -> SessionResponse:
        study_session, membership = await self._session_and_membership(session, session_id, actor)
        self._require_can_manage(study_session, actor, membership)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise AppError(code="empty_update", message="No fields to update", status_code=400)

        # A partial update can move either edge of the window, so validate the
        # merged result rather than the request on its own.
        start = data.get("start_time", study_session.start_time)
        end = data.get("end_time", study_session.end_time)
        try:
            validate_window(start, end)
        except ValueError as exc:
            raise AppError(
                code="invalid_time_window", message=str(exc), status_code=422
            ) from exc

        if "title" in data:
            title = (data["title"] or "").strip()
            if not title:
                raise AppError(
                    code="validation_error", message="Title cannot be empty", status_code=422
                )
            data["title"] = title

        for field, value in data.items():
            setattr(study_session, field, value)
        await session.flush()
        return await self._response_for(session, study_session.id, actor, membership)

    async def delete_session(
        self, session: AsyncSession, *, session_id: UUID, actor: User
    ) -> None:
        study_session, membership = await self._session_and_membership(session, session_id, actor)
        self._require_can_manage(study_session, actor, membership)
        await self.sessions.delete(session, study_session)

    async def set_rsvp(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        actor: User,
        status: RsvpStatus,
    ) -> SessionResponse:
        """Idempotent: answering twice updates the answer, never duplicates it."""
        study_session, membership = await self._session_and_membership(session, session_id, actor)

        existing = await self.sessions.get_rsvp(
            session, session_id=study_session.id, user_id=actor.id
        )
        previous = existing.status if existing is not None else None
        if existing is None:
            await self.sessions.add_rsvp(
                session,
                SessionRsvp(session_id=study_session.id, user_id=actor.id, status=status),
            )
        else:
            existing.status = status
            await session.flush()

        if previous != status:
            group = await self.groups.get_by_id(session, study_session.group_id)
            if group is not None:
                await notification_service.notify_rsvp_updated(
                    session,
                    actor=actor,
                    organizer_id=study_session.created_by,
                    group_id=study_session.group_id,
                    group_name=group.name,
                    session_id=study_session.id,
                    session_title=study_session.title,
                    status=status.value,
                )
        return await self._response_for(session, study_session.id, actor, membership)

    async def clear_rsvp(
        self, session: AsyncSession, *, session_id: UUID, actor: User
    ) -> SessionResponse:
        study_session, membership = await self._session_and_membership(session, session_id, actor)
        existing = await self.sessions.get_rsvp(
            session, session_id=study_session.id, user_id=actor.id
        )
        if existing is not None:
            await self.sessions.delete_rsvp(session, existing)
        return await self._response_for(session, study_session.id, actor, membership)

    async def list_attendees(
        self, session: AsyncSession, *, session_id: UUID, actor: User
    ) -> list[SessionAttendee]:
        study_session, _membership = await self._session_and_membership(session, session_id, actor)
        rows = await self.sessions.list_attendees(session, session_id=study_session.id)
        return [
            SessionAttendee(
                user=SessionUser.model_validate(user),
                status=rsvp.status,
                responded_at=rsvp.responded_at,
            )
            for rsvp, user in rows
        ]

    async def list_my_sessions(
        self, session: AsyncSession, *, actor: User, limit: int
    ) -> list[MySessionResponse]:
        rows = await self.sessions.list_upcoming_for_user(
            session, user_id=actor.id, now=_now(), limit=limit
        )
        return [
            MySessionResponse(
                **_to_response(
                    study_session,
                    creator,
                    going,
                    maybe,
                    declined,
                    my_status,
                    actor=actor,
                    membership=None,
                ).model_dump(),
                group_name=group_name,
            )
            for study_session, creator, going, maybe, declined, my_status, group_name in rows
        ]

    async def _membership(
        self, session: AsyncSession, group_id: UUID, user_id: UUID
    ) -> tuple[object, GroupMembership]:
        return await require_group_and_membership(
            session,
            groups=self.groups,
            memberships=self.memberships,
            group_id=group_id,
            user_id=user_id,
        )

    async def _session_and_membership(
        self, session: AsyncSession, session_id: UUID, actor: User
    ) -> tuple[StudySession, GroupMembership]:
        """Authorize against the session's *own* group, so an id from another
        group cannot be used to read or edit it."""
        study_session = await self.sessions.get_by_id(session, session_id)
        if study_session is None:
            raise AppError(
                code="session_not_found", message="Study session not found", status_code=404
            )
        _group, membership = await self._membership(session, study_session.group_id, actor.id)
        return study_session, membership

    def _require_can_manage(
        self, study_session: StudySession, actor: User, membership: GroupMembership
    ) -> None:
        if study_session.created_by != actor.id and not is_owner_or_admin(membership):
            raise AppError(
                code="forbidden",
                message="Only the organiser or a group owner/admin can change this session",
                status_code=403,
            )

    async def _response_for(
        self,
        session: AsyncSession,
        session_id: UUID,
        actor: User,
        membership: GroupMembership,
    ) -> SessionResponse:
        row = await self.sessions.get_with_details(
            session, session_id=session_id, user_id=actor.id
        )
        if row is None:
            raise AppError(
                code="session_not_found", message="Study session not found", status_code=404
            )
        return _to_response(*row, actor=actor, membership=membership)


def _to_response(
    study_session: StudySession,
    creator: User,
    going: int,
    maybe: int,
    declined: int,
    my_status: RsvpStatus | None,
    *,
    actor: User | None,
    membership: GroupMembership | None,
) -> SessionResponse:
    can_manage = False
    if actor is not None:
        can_manage = study_session.created_by == actor.id or (
            membership is not None and is_owner_or_admin(membership)
        )
    return SessionResponse(
        id=study_session.id,
        group_id=study_session.group_id,
        title=study_session.title,
        description=study_session.description,
        location=study_session.location,
        start_time=study_session.start_time,
        end_time=study_session.end_time,
        created_by=study_session.created_by,
        created_at=study_session.created_at,
        updated_at=study_session.updated_at,
        creator=SessionUser.model_validate(creator),
        rsvp_counts=RsvpCounts(going=going, maybe=maybe, declined=declined),
        my_rsvp=my_status,
        can_manage=can_manage,
    )


session_service = SessionService()
