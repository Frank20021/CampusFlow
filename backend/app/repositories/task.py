from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.membership import GroupMembership
from app.models.study_group import StudyGroup
from app.models.task import Task, TaskStatus
from app.models.user import User

# Two aliases so assignee and creator can be joined in the same statement.
# Without this, rendering a board would issue one query per task (N+1).
Assignee = aliased(User)
Creator = aliased(User)

TaskRow = tuple[Task, User | None, User]


def _base_select() -> Select:
    return (
        select(Task, Assignee, Creator)
        .outerjoin(Assignee, Assignee.id == Task.assigned_to)
        .join(Creator, Creator.id == Task.created_by)
    )


class TaskRepository:
    async def get_by_id(self, session: AsyncSession, task_id: UUID) -> Task | None:
        return await session.get(Task, task_id)

    async def get_with_people(self, session: AsyncSession, task_id: UUID) -> TaskRow | None:
        row = (await session.execute(_base_select().where(Task.id == task_id))).first()
        if row is None:
            return None
        return row[0], row[1], row[2]

    async def add(self, session: AsyncSession, task: Task) -> Task:
        session.add(task)
        await session.flush()
        return task

    async def delete(self, session: AsyncSession, task: Task) -> None:
        await session.delete(task)
        await session.flush()

    async def list_for_group(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        status: TaskStatus | None,
        assigned_to: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[TaskRow], int]:
        stmt = _base_select().where(Task.group_id == group_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if assigned_to is not None:
            stmt = stmt.where(Task.assigned_to == assigned_to)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        ordered = stmt.order_by(
            Task.due_date.asc().nulls_last(),
            Task.created_at.asc(),
        ).limit(limit).offset(offset)
        rows = (await session.execute(ordered)).all()
        return [(row[0], row[1], row[2]) for row in rows], total

    async def list_assigned_to_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        include_done: bool,
        limit: int,
    ) -> list[tuple[Task, User | None, User, str]]:
        """Tasks assigned to a user across every group they belong to.

        The membership join keeps the result correct if the user was removed
        from a group without their assignment being cleared.
        """
        stmt = (
            _base_select()
            .add_columns(StudyGroup.name)
            .join(StudyGroup, StudyGroup.id == Task.group_id)
            .join(
                GroupMembership,
                (GroupMembership.group_id == Task.group_id)
                & (GroupMembership.user_id == user_id),
            )
            .where(Task.assigned_to == user_id)
        )
        if not include_done:
            stmt = stmt.where(Task.status != TaskStatus.DONE)

        ordered = stmt.order_by(
            Task.due_date.asc().nulls_last(),
            Task.created_at.asc(),
        ).limit(limit)
        rows = (await session.execute(ordered)).all()
        return [(row[0], row[1], row[2], row[3]) for row in rows]

    async def clear_assignments_for_member(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        user_id: UUID,
    ) -> None:
        """Unassign a user from a group's tasks when they lose membership.

        A single UPDATE rather than loading rows into Python; the column's
        onupdate default refreshes updated_at.
        """
        await session.execute(
            update(Task)
            .where(Task.group_id == group_id, Task.assigned_to == user_id)
            .values(assigned_to=None)
        )
