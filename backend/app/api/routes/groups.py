from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.schemas.common import Paginated
from app.schemas.group import (
    GroupCreateRequest,
    GroupResponse,
    GroupUpdateRequest,
    MemberResponse,
    MemberRoleUpdateRequest,
)
from app.services.group import group_service

router = APIRouter()


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> GroupResponse:
    return await group_service.create_group(session, owner=current_user, payload=payload)


@router.get("", response_model=Paginated[GroupResponse])
async def list_groups(
    current_user: CurrentUser,
    session: DbSession,
    pagination: Pagination,
    mine: Annotated[bool, Query()] = False,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> Paginated[GroupResponse]:
    limit, offset = pagination
    return await group_service.list_groups(
        session,
        user_id=current_user.id,
        mine_only=mine,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> GroupResponse:
    return await group_service.get_group(session, group_id=group_id, user_id=current_user.id)


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: UUID,
    payload: GroupUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> GroupResponse:
    return await group_service.update_group(
        session, group_id=group_id, actor=current_user, payload=payload
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await group_service.delete_group(session, group_id=group_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/join", response_model=GroupResponse)
async def join_group(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> GroupResponse:
    return await group_service.join_group(session, group_id=group_id, actor=current_user)


@router.delete("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await group_service.leave_group(session, group_id=group_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/members", response_model=list[MemberResponse])
async def list_members(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[MemberResponse]:
    return await group_service.list_members(session, group_id=group_id, actor=current_user)


@router.patch("/{group_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    group_id: UUID,
    user_id: UUID,
    payload: MemberRoleUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MemberResponse:
    return await group_service.update_member_role(
        session,
        group_id=group_id,
        target_user_id=user_id,
        actor=current_user,
        role=payload.role,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await group_service.remove_member(
        session,
        group_id=group_id,
        target_user_id=user_id,
        actor=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
