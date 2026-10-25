from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.membership import GroupMembership
from app.models.user import User


class MembershipRepository:
    async def get(self, session: AsyncSession, *, user_id: UUID, group_id: UUID) -> GroupMembership | None:
        stmt = select(GroupMembership).where(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def add(self, session: AsyncSession, membership: GroupMembership) -> GroupMembership:
        session.add(membership)
        await session.flush()
        return membership

    async def delete(self, session: AsyncSession, membership: GroupMembership) -> None:
        await session.delete(membership)
        await session.flush()

    async def list_user_ids(self, session: AsyncSession, group_id: UUID) -> list[UUID]:
        stmt = select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)
        return list((await session.execute(stmt)).scalars().all())

    async def list_for_group(
        self,
        session: AsyncSession,
        group_id: UUID,
    ) -> list[tuple[GroupMembership, User]]:
        stmt = (
            select(GroupMembership, User)
            .join(User, User.id == GroupMembership.user_id)
            .where(GroupMembership.group_id == group_id)
            .order_by(GroupMembership.joined_at.asc())
            .options(selectinload(GroupMembership.user))
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
