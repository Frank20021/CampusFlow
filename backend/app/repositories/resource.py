from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource
from app.models.user import User

ResourceRow = tuple[Resource, User]


def _base_select() -> Select:
    return select(Resource, User).join(User, User.id == Resource.created_by)


class ResourceRepository:
    async def get_by_id(self, session: AsyncSession, resource_id: UUID) -> Resource | None:
        return await session.get(Resource, resource_id)

    async def add(self, session: AsyncSession, resource: Resource) -> Resource:
        session.add(resource)
        await session.flush()
        return resource

    async def delete(self, session: AsyncSession, resource: Resource) -> None:
        await session.delete(resource)
        await session.flush()

    async def get_with_creator(
        self, session: AsyncSession, resource_id: UUID
    ) -> ResourceRow | None:
        row = (await session.execute(_base_select().where(Resource.id == resource_id))).first()
        return (row[0], row[1]) if row else None

    async def list_for_group(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ResourceRow], int]:
        stmt = _base_select().where(Resource.group_id == group_id)
        if search:
            # ILIKE over title and description. Fine at a study group's scale;
            # a full-text index is the move if a group ever has thousands.
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Resource.title.ilike(pattern), Resource.description.ilike(pattern))
            )

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        ordered = (
            stmt.order_by(Resource.created_at.desc(), Resource.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await session.execute(ordered)).all()
        return [(row[0], row[1]) for row in rows], total
