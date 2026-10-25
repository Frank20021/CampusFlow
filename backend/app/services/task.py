from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.membership import GroupMembership
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.task import TaskRepository
from app.schemas.common import Paginated
from app.schemas.task import (
    MyTaskResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    TaskUser,
)
from app.services.access import is_owner_or_admin, require_group_and_membership
from app.services.notification import notification_service


class TaskService:
    """Task rules.

    Chosen: any member of a group may create, edit, and move any task on that
    group's board, because a study group is a small trusted team and a shared
    board is the point. Deletion is narrower — creator, or an owner/admin for
    moderation — since deletion is the only destructive action.
    Alternative: per-task ownership on edits. Tradeoff: safer, but it makes
    the common case (a classmate fixing a due date) require an admin.
    """

    def __init__(
        self,
        tasks: TaskRepository | None = None,
        groups: GroupRepository | None = None,
        memberships: MembershipRepository | None = None,
    ) -> None:
        self.tasks = tasks or TaskRepository()
        self.groups = groups or GroupRepository()
        self.memberships = memberships or MembershipRepository()

    async def create_task(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        payload: TaskCreateRequest,
    ) -> TaskResponse:
        group, membership = await self._membership(session, group_id, actor.id)
        if payload.assigned_to is not None:
            await self._require_assignee_is_member(session, group_id, payload.assigned_to)

        task = Task(
            group_id=group_id,
            title=payload.title,
            description=payload.description,
            assigned_to=payload.assigned_to,
            created_by=actor.id,
            status=payload.status,
            priority=payload.priority,
            due_date=payload.due_date,
        )
        task = await self.tasks.add(session, task)
        if task.assigned_to is not None:
            await notification_service.notify_task_assigned(
                session,
                actor=actor,
                assignee_id=task.assigned_to,
                group_id=group_id,
                group_name=group.name,
                task_id=task.id,
                task_title=task.title,
            )
        return await self._response_for(session, task.id, membership, actor=actor)

    async def list_tasks(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        status: TaskStatus | None,
        assigned_to: UUID | None,
        limit: int,
        offset: int,
    ) -> Paginated[TaskResponse]:
        _group, membership = await self._membership(session, group_id, actor.id)
        rows, total = await self.tasks.list_for_group(
            session,
            group_id=group_id,
            status=status,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )
        items = [_to_response(task, assignee, creator, actor, membership) for task, assignee, creator in rows]
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def get_task(self, session: AsyncSession, *, task_id: UUID, actor: User) -> TaskResponse:
        task, membership = await self._task_and_membership(session, task_id, actor)
        return await self._response_for(session, task.id, membership, actor=actor)

    async def update_task(
        self,
        session: AsyncSession,
        *,
        task_id: UUID,
        actor: User,
        payload: TaskUpdateRequest,
    ) -> TaskResponse:
        task, membership = await self._task_and_membership(session, task_id, actor)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise AppError(code="empty_update", message="No fields to update", status_code=400)

        if "assigned_to" in data and data["assigned_to"] is not None:
            await self._require_assignee_is_member(session, task.group_id, data["assigned_to"])

        previous_assignee = task.assigned_to
        for field, value in data.items():
            setattr(task, field, value)
        await session.flush()

        new_assignee = task.assigned_to
        if new_assignee is not None and new_assignee != previous_assignee:
            group = await self.groups.get_by_id(session, task.group_id)
            if group is not None:
                await notification_service.notify_task_assigned(
                    session,
                    actor=actor,
                    assignee_id=new_assignee,
                    group_id=task.group_id,
                    group_name=group.name,
                    task_id=task.id,
                    task_title=task.title,
                )
        return await self._response_for(session, task.id, membership, actor=actor)

    async def delete_task(self, session: AsyncSession, *, task_id: UUID, actor: User) -> None:
        task, membership = await self._task_and_membership(session, task_id, actor)
        if task.created_by != actor.id and not is_owner_or_admin(membership):
            raise AppError(
                code="forbidden",
                message="Only the task creator or a group owner/admin can delete this task",
                status_code=403,
            )
        await self.tasks.delete(session, task)

    async def list_my_tasks(
        self,
        session: AsyncSession,
        *,
        actor: User,
        include_done: bool,
        limit: int,
    ) -> list[MyTaskResponse]:
        rows = await self.tasks.list_assigned_to_user(
            session,
            user_id=actor.id,
            include_done=include_done,
            limit=limit,
        )
        return [
            MyTaskResponse(
                **_to_response(task, assignee, creator, actor, membership=None).model_dump(),
                group_name=group_name,
            )
            for task, assignee, creator, group_name in rows
        ]

    async def _membership(
        self,
        session: AsyncSession,
        group_id: UUID,
        user_id: UUID,
    ) -> tuple[object, GroupMembership]:
        return await require_group_and_membership(
            session,
            groups=self.groups,
            memberships=self.memberships,
            group_id=group_id,
            user_id=user_id,
        )

    async def _task_and_membership(
        self,
        session: AsyncSession,
        task_id: UUID,
        actor: User,
    ) -> tuple[Task, GroupMembership]:
        """Load a task, then authorize against *that task's* group.

        This is the check that stops a member of group A from editing a task
        in group B by guessing its id.
        """
        task = await self.tasks.get_by_id(session, task_id)
        if task is None:
            raise AppError(code="task_not_found", message="Task not found", status_code=404)
        _group, membership = await self._membership(session, task.group_id, actor.id)
        return task, membership

    async def _require_assignee_is_member(
        self,
        session: AsyncSession,
        group_id: UUID,
        user_id: UUID,
    ) -> None:
        membership = await self.memberships.get(session, user_id=user_id, group_id=group_id)
        if membership is None:
            raise AppError(
                code="assignee_not_member",
                message="Tasks can only be assigned to members of this group",
                status_code=422,
            )

    async def _response_for(
        self,
        session: AsyncSession,
        task_id: UUID,
        membership: GroupMembership,
        *,
        actor: User | None = None,
    ) -> TaskResponse:
        row = await self.tasks.get_with_people(session, task_id)
        if row is None:
            raise AppError(code="task_not_found", message="Task not found", status_code=404)
        task, assignee, creator = row
        return _to_response(task, assignee, creator, actor, membership)


def _to_response(
    task: Task,
    assignee: User | None,
    creator: User,
    actor: User | None,
    membership: GroupMembership | None,
) -> TaskResponse:
    can_delete = False
    if actor is not None:
        can_delete = task.created_by == actor.id or (
            membership is not None and is_owner_or_admin(membership)
        )
    return TaskResponse(
        id=task.id,
        group_id=task.group_id,
        title=task.title,
        description=task.description,
        assigned_to=task.assigned_to,
        created_by=task.created_by,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
        assignee=TaskUser.model_validate(assignee) if assignee is not None else None,
        creator=TaskUser.model_validate(creator),
        can_delete=can_delete,
    )


task_service = TaskService()
