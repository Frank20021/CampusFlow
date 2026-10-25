from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.membership import GroupMembership
from app.models.study_group import StudyGroup
from app.models.study_session import RsvpStatus, SessionRsvp, StudySession
from app.models.user import User

# The caller's own RSVP, joined rather than fetched per row.
MyRsvp = aliased(SessionRsvp)

# (session, creator, going, maybe, declined, my_status)
SessionRow = tuple[StudySession, User, int, int, int, RsvpStatus | None]


def _counts_subquery():
    """One aggregate pass over the RSVPs, joined back by session.

    Chosen over three correlated subqueries per row: this scans the RSVP
    index once for the whole page instead of once per status per session.
    `count(*) FILTER (...)` keeps all three totals in a single GROUP BY.
    """
    return (
        select(
            SessionRsvp.session_id.label("session_id"),
            func.count().filter(SessionRsvp.status == RsvpStatus.GOING).label("going"),
            func.count().filter(SessionRsvp.status == RsvpStatus.MAYBE).label("maybe"),
            func.count().filter(SessionRsvp.status == RsvpStatus.DECLINED).label("declined"),
        )
        .group_by(SessionRsvp.session_id)
        .subquery()
    )


def _base_select(user_id: UUID) -> Select:
    counts = _counts_subquery()
    return (
        select(
            StudySession,
            User,
            func.coalesce(counts.c.going, 0),
            func.coalesce(counts.c.maybe, 0),
            func.coalesce(counts.c.declined, 0),
            MyRsvp.status,
        )
        .join(User, User.id == StudySession.created_by)
        .outerjoin(counts, counts.c.session_id == StudySession.id)
        .outerjoin(
            MyRsvp,
            (MyRsvp.session_id == StudySession.id) & (MyRsvp.user_id == user_id),
        )
    )


def _as_rows(rows) -> list[SessionRow]:
    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]


class SessionRepository:
    async def get_by_id(self, session: AsyncSession, session_id: UUID) -> StudySession | None:
        return await session.get(StudySession, session_id)

    async def add(self, session: AsyncSession, study_session: StudySession) -> StudySession:
        session.add(study_session)
        await session.flush()
        return study_session

    async def delete(self, session: AsyncSession, study_session: StudySession) -> None:
        await session.delete(study_session)
        await session.flush()

    async def get_with_details(
        self, session: AsyncSession, *, session_id: UUID, user_id: UUID
    ) -> SessionRow | None:
        stmt = _base_select(user_id).where(StudySession.id == session_id)
        row = (await session.execute(stmt)).first()
        return _as_rows([row])[0] if row else None

    async def list_for_group(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        user_id: UUID,
        upcoming_only: bool,
        starts_after: datetime | None,
        starts_before: datetime | None,
        now: datetime,
        limit: int,
        offset: int,
    ) -> tuple[list[SessionRow], int]:
        stmt = _base_select(user_id).where(StudySession.group_id == group_id)

        if upcoming_only:
            # Compare on end_time: a session that started an hour ago but runs
            # until tonight is still "upcoming" to someone deciding to join.
            stmt = stmt.where(StudySession.end_time >= now)
        if starts_after is not None:
            stmt = stmt.where(StudySession.start_time >= starts_after)
        if starts_before is not None:
            stmt = stmt.where(StudySession.start_time < starts_before)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        ordered = (
            stmt.order_by(StudySession.start_time.asc(), StudySession.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return _as_rows((await session.execute(ordered)).all()), total

    async def list_upcoming_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        now: datetime,
        limit: int,
    ) -> list[tuple[StudySession, User, int, int, int, RsvpStatus | None, str]]:
        """Upcoming sessions across every group the user belongs to.

        The membership join is what scopes this: leaving a group removes its
        sessions from the dashboard without touching the sessions themselves.
        """
        stmt = (
            _base_select(user_id)
            .add_columns(StudyGroup.name)
            .join(StudyGroup, StudyGroup.id == StudySession.group_id)
            .join(
                GroupMembership,
                (GroupMembership.group_id == StudySession.group_id)
                & (GroupMembership.user_id == user_id),
            )
            .where(StudySession.end_time >= now)
            .order_by(StudySession.start_time.asc(), StudySession.id.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows]

    async def get_rsvp(
        self, session: AsyncSession, *, session_id: UUID, user_id: UUID
    ) -> SessionRsvp | None:
        stmt = select(SessionRsvp).where(
            SessionRsvp.session_id == session_id, SessionRsvp.user_id == user_id
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def add_rsvp(self, session: AsyncSession, rsvp: SessionRsvp) -> SessionRsvp:
        session.add(rsvp)
        await session.flush()
        return rsvp

    async def delete_rsvp(self, session: AsyncSession, rsvp: SessionRsvp) -> None:
        await session.delete(rsvp)
        await session.flush()

    async def list_attendees(
        self, session: AsyncSession, *, session_id: UUID
    ) -> list[tuple[SessionRsvp, User]]:
        stmt = (
            select(SessionRsvp, User)
            .join(User, User.id == SessionRsvp.user_id)
            .where(SessionRsvp.session_id == session_id)
            .order_by(User.first_name.asc(), User.last_name.asc())
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
