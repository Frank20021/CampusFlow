from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User

NotificationRow = tuple[Notification, User | None]


class NotificationRepository:
    async def get_by_id(
        self, session: AsyncSession, notification_id: UUID
    ) -> Notification | None:
        return await session.get(Notification, notification_id)

    async def get_with_actor(
        self, session: AsyncSession, notification_id: UUID
    ) -> NotificationRow | None:
        stmt = (
            select(Notification, User)
            .outerjoin(User, User.id == Notification.actor_id)
            .where(Notification.id == notification_id)
        )
        row = (await session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def add_many(
        self, session: AsyncSession, notifications: list[Notification]
    ) -> list[Notification]:
        session.add_all(notifications)
        await session.flush()
        return notifications

    async def list_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[NotificationRow], int]:
        filters = [Notification.user_id == user_id]
        if unread_only:
            filters.append(Notification.read_at.is_(None))

        total = await session.scalar(
            select(func.count()).select_from(Notification).where(*filters)
        )
        stmt = (
            select(Notification, User)
            .outerjoin(User, User.id == Notification.actor_id)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], int(total or 0)

    async def list_after(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        after: tuple[datetime, UUID],
        limit: int,
    ) -> list[NotificationRow]:
        stmt = (
            select(Notification, User)
            .outerjoin(User, User.id == Notification.actor_id)
            .where(Notification.user_id == user_id)
            .where(tuple_(Notification.created_at, Notification.id) > after)
            .order_by(Notification.created_at.asc(), Notification.id.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def unread_count(self, session: AsyncSession, *, user_id: UUID) -> int:
        total = await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return int(total or 0)

    async def mark_read(
        self, session: AsyncSession, notification: Notification, *, when: datetime
    ) -> None:
        if notification.read_at is None:
            notification.read_at = when
            await session.flush()

    async def mark_all_read(
        self, session: AsyncSession, *, user_id: UUID, when: datetime
    ) -> int:
        result = await session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=when)
        )
        return int(result.rowcount or 0)
