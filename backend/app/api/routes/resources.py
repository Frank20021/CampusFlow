from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.schemas.common import Paginated
from app.schemas.resource import (
    ResourceCreateRequest,
    ResourceResponse,
    ResourceUpdateRequest,
)
from app.services.resource import resource_service

group_resources_router = APIRouter()
resources_router = APIRouter()


@group_resources_router.post(
    "/{group_id}/resources",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource(
    group_id: UUID,
    payload: ResourceCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ResourceResponse:
    return await resource_service.create_resource(
        session, group_id=group_id, actor=current_user, payload=payload
    )


@group_resources_router.get(
    "/{group_id}/resources", response_model=Paginated[ResourceResponse]
)
async def list_resources(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Paginated[ResourceResponse]:
    limit, offset = pagination
    return await resource_service.list_resources(
        session,
        group_id=group_id,
        actor=current_user,
        search=search,
        limit=limit,
        offset=offset,
    )


@resources_router.patch("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: UUID,
    payload: ResourceUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ResourceResponse:
    return await resource_service.update_resource(
        session, resource_id=resource_id, actor=current_user, payload=payload
    )


@resources_router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await resource_service.delete_resource(
        session, resource_id=resource_id, actor=current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
