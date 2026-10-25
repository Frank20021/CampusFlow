"""Task routes.

Creating and listing are group-scoped (`/api/groups/{group_id}/tasks`) because
a task only exists inside a group. Mutating a single task uses the flat
`/api/tasks/{task_id}` form: the group is derived from the task, and the
service authorizes against that group.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.task import TaskStatus
from app.schemas.common import Paginated
from app.schemas.task import MyTaskResponse, TaskCreateRequest, TaskResponse, TaskUpdateRequest
from app.services.task import task_service

# Boards read a whole group at once, so the default page is larger than the
# generic list pagination while still being bounded.
def board_pagination(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    return limit, offset


BoardPagination = Annotated[tuple[int, int], Depends(board_pagination)]

group_tasks_router = APIRouter()
tasks_router = APIRouter()


@group_tasks_router.post(
    "/{group_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    group_id: UUID,
    payload: TaskCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    return await task_service.create_task(
        session, group_id=group_id, actor=current_user, payload=payload
    )


@group_tasks_router.get("/{group_id}/tasks", response_model=Paginated[TaskResponse])
async def list_tasks(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    pagination: BoardPagination,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    assigned_to: Annotated[UUID | None, Query()] = None,
) -> Paginated[TaskResponse]:
    limit, offset = pagination
    return await task_service.list_tasks(
        session,
        group_id=group_id,
        actor=current_user,
        status=task_status,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )


@tasks_router.get("/mine", response_model=list[MyTaskResponse])
async def list_my_tasks(
    current_user: CurrentUser,
    session: DbSession,
    include_done: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MyTaskResponse]:
    """Tasks assigned to the caller across all of their groups."""
    return await task_service.list_my_tasks(
        session, actor=current_user, include_done=include_done, limit=limit
    )


@tasks_router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    return await task_service.get_task(session, task_id=task_id, actor=current_user)


@tasks_router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    payload: TaskUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    return await task_service.update_task(
        session, task_id=task_id, actor=current_user, payload=payload
    )


@tasks_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await task_service.delete_task(session, task_id=task_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
