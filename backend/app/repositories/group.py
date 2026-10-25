from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.membership import GroupMembership, MembershipRole
from app.models.study_group import StudyGroup


class GroupRepository:
    async def get_by_id(self, session: AsyncSession, group_id: UUID) -> StudyGroup | None:
        return await session.get(StudyGroup, group_id)

    async def add(self, session: AsyncSession, group: StudyGroup) -> StudyGroup:
        session.add(group)
        await session.flush()
        return group

    async def delete(self, session: AsyncSession, group: StudyGroup) -> None:
        await session.delete(group)
        await session.flush()

    async def list_groups(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        mine_only: bool,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[StudyGroup, int, MembershipRole | None]], int]:
        """Return groups with member_count and the caller's role in one query.

        Two aliases of group_memberships: one for the count join, one for the
        current user's membership. This avoids the N+1 pattern of querying
        members per group in a Python loop.
        """
        count_membership = aliased(GroupMembership)
        my_membership = aliased(GroupMembership)

        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    StudyGroup.name.ilike(pattern),
                    StudyGroup.course_code.ilike(pattern),
                    StudyGroup.description.ilike(pattern),
                )
            )
        if mine_only:
            filters.append(my_membership.id.is_not(None))

        base = (
            select(
                StudyGroup,
                func.count(func.distinct(count_membership.id)).label("member_count"),
                my_membership.role.label("my_role"),
            )
            .outerjoin(count_membership, count_membership.group_id == StudyGroup.id)
            .outerjoin(
                my_membership,
                (my_membership.group_id == StudyGroup.id) & (my_membership.user_id == user_id),
            )
        )
        if filters:
            base = base.where(*filters)

        grouped: Select = base.group_by(StudyGroup.id, my_membership.role).order_by(
            StudyGroup.created_at.desc()
        )

        total_stmt = select(func.count()).select_from(grouped.subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        page_stmt = grouped.limit(limit).offset(offset)
        rows = (await session.execute(page_stmt)).all()
        return [(row[0], int(row[1]), row[2]) for row in rows], total

    async def get_with_counts(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        user_id: UUID,
    ) -> tuple[StudyGroup, int, MembershipRole | None] | None:
        count_membership = aliased(GroupMembership)
        my_membership = aliased(GroupMembership)
        stmt = (
            select(
                StudyGroup,
                func.count(func.distinct(count_membership.id)).label("member_count"),
                my_membership.role.label("my_role"),
            )
            .outerjoin(count_membership, count_membership.group_id == StudyGroup.id)
            .outerjoin(
                my_membership,
                (my_membership.group_id == StudyGroup.id) & (my_membership.user_id == user_id),
            )
            .where(StudyGroup.id == group_id)
            .group_by(StudyGroup.id, my_membership.role)
        )
        row = (await session.execute(stmt)).first()
        if row is None:
            return None
        return row[0], int(row[1]), row[2]
