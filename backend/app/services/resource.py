"""Shared links.

Deletion follows the spec — students delete resources they created — widened
to owners and admins, who are the ones expected to remove inappropriate
content. Editing is the same set, for the same reason.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.membership import GroupMembership
from app.models.resource import Resource
from app.models.user import User
from app.repositories import (
    group_repository,
    membership_repository,
    resource_repository,
)
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.resource import ResourceRepository
from app.schemas.common import Paginated
from app.schemas.resource import (
    ResourceCreateRequest,
    ResourceResponse,
    ResourceUpdateRequest,
    ResourceUser,
)
from app.services.access import is_owner_or_admin, require_group_and_membership
from app.services.notification import notification_service


class ResourceService:
    def __init__(
        self,
        resources: ResourceRepository | None = None,
        groups: GroupRepository | None = None,
        memberships: MembershipRepository | None = None,
    ) -> None:
        self.resources = resources or resource_repository
        self.groups = groups or group_repository
        self.memberships = memberships or membership_repository

    async def create_resource(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        payload: ResourceCreateRequest,
    ) -> ResourceResponse:
        group, membership = await self._membership(session, group_id, actor.id)
        resource = Resource(
            group_id=group_id,
            title=payload.title,
            url=payload.url,
            description=payload.description,
            created_by=actor.id,
        )
        await self.resources.add(session, resource)
        await notification_service.notify_resource_shared(
            session,
            actor=actor,
            group_id=group_id,
            group_name=group.name,
            resource_id=resource.id,
            resource_title=resource.title,
        )
        return await self._response_for(session, resource.id, actor, membership)

    async def list_resources(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        search: str | None,
        limit: int,
        offset: int,
    ) -> Paginated[ResourceResponse]:
        _group, membership = await self._membership(session, group_id, actor.id)
        rows, total = await self.resources.list_for_group(
            session, group_id=group_id, search=search, limit=limit, offset=offset
        )
        items = [
            _to_response(resource, creator, actor, membership) for resource, creator in rows
        ]
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def update_resource(
        self,
        session: AsyncSession,
        *,
        resource_id: UUID,
        actor: User,
        payload: ResourceUpdateRequest,
    ) -> ResourceResponse:
        resource, membership = await self._resource_and_membership(session, resource_id, actor)
        self._require_can_manage(resource, actor, membership)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise AppError(code="empty_update", message="No fields to update", status_code=400)
        for field, value in data.items():
            setattr(resource, field, value)
        await session.flush()
        return await self._response_for(session, resource.id, actor, membership)

    async def delete_resource(
        self, session: AsyncSession, *, resource_id: UUID, actor: User
    ) -> None:
        resource, membership = await self._resource_and_membership(session, resource_id, actor)
        self._require_can_manage(resource, actor, membership)
        await self.resources.delete(session, resource)

    async def _membership(
        self, session: AsyncSession, group_id: UUID, user_id: UUID
    ) -> tuple[object, GroupMembership]:
        return await require_group_and_membership(
            session,
            groups=self.groups,
            memberships=self.memberships,
            group_id=group_id,
            user_id=user_id,
        )

    async def _resource_and_membership(
        self, session: AsyncSession, resource_id: UUID, actor: User
    ) -> tuple[Resource, GroupMembership]:
        resource = await self.resources.get_by_id(session, resource_id)
        if resource is None:
            raise AppError(code="resource_not_found", message="Resource not found", status_code=404)
        _group, membership = await self._membership(session, resource.group_id, actor.id)
        return resource, membership

    def _require_can_manage(
        self, resource: Resource, actor: User, membership: GroupMembership
    ) -> None:
        if resource.created_by != actor.id and not is_owner_or_admin(membership):
            raise AppError(
                code="forbidden",
                message="You can only change resources you added",
                status_code=403,
            )

    async def _response_for(
        self,
        session: AsyncSession,
        resource_id: UUID,
        actor: User,
        membership: GroupMembership,
    ) -> ResourceResponse:
        row = await self.resources.get_with_creator(session, resource_id)
        if row is None:
            raise AppError(code="resource_not_found", message="Resource not found", status_code=404)
        resource, creator = row
        return _to_response(resource, creator, actor, membership)


def _to_response(
    resource: Resource,
    creator: User,
    actor: User | None,
    membership: GroupMembership | None,
) -> ResourceResponse:
    can_delete = False
    if actor is not None:
        can_delete = resource.created_by == actor.id or (
            membership is not None and is_owner_or_admin(membership)
        )
    return ResourceResponse(
        id=resource.id,
        group_id=resource.group_id,
        title=resource.title,
        url=resource.url,
        description=resource.description,
        created_by=resource.created_by,
        created_at=resource.created_at,
        creator=ResourceUser.model_validate(creator),
        can_delete=can_delete,
    )


resource_service = ResourceService()
