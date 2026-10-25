from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.membership import GroupMembership, MembershipRole
from app.models.study_group import StudyGroup
from app.models.user import User
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.task import TaskRepository
from app.schemas.common import Paginated
from app.schemas.group import (
    GroupCreateRequest,
    GroupResponse,
    GroupUpdateRequest,
    MemberResponse,
    MemberRoleLiteral,
)
from app.services.access import (
    require_group_and_membership,
    require_owner as _require_owner,
    require_owner_or_admin as _require_owner_or_admin,
)


class GroupService:
    def __init__(
        self,
        groups: GroupRepository | None = None,
        memberships: MembershipRepository | None = None,
        tasks: TaskRepository | None = None,
    ) -> None:
        self.groups = groups or GroupRepository()
        self.memberships = memberships or MembershipRepository()
        self.tasks = tasks or TaskRepository()

    async def create_group(
        self,
        session: AsyncSession,
        *,
        owner: User,
        payload: GroupCreateRequest,
    ) -> GroupResponse:
        group = StudyGroup(
            name=payload.name,
            description=payload.description,
            course_code=payload.course_code,
            owner_id=owner.id,
        )
        group = await self.groups.add(session, group)
        await self.memberships.add(
            session,
            GroupMembership(user_id=owner.id, group_id=group.id, role=MembershipRole.OWNER),
        )
        return GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            course_code=group.course_code,
            owner_id=group.owner_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            member_count=1,
            my_role=MembershipRole.OWNER,
        )

    async def list_groups(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        mine_only: bool,
        search: str | None,
        limit: int,
        offset: int,
    ) -> Paginated[GroupResponse]:
        rows, total = await self.groups.list_groups(
            session,
            user_id=user_id,
            mine_only=mine_only,
            search=search,
            limit=limit,
            offset=offset,
        )
        items = [_to_group_response(group, count, role) for group, count, role in rows]
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def get_group(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        user_id: UUID,
    ) -> GroupResponse:
        row = await self.groups.get_with_counts(session, group_id=group_id, user_id=user_id)
        if row is None:
            raise AppError(code="group_not_found", message="Study group not found", status_code=404)
        group, count, role = row
        return _to_group_response(group, count, role)

    async def update_group(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        payload: GroupUpdateRequest,
    ) -> GroupResponse:
        group, membership = await self._require_group_and_membership(session, group_id, actor.id)
        _require_owner_or_admin(membership)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise AppError(code="empty_update", message="No fields to update", status_code=400)
        for field, value in data.items():
            setattr(group, field, value)
        await session.flush()
        return await self.get_group(session, group_id=group.id, user_id=actor.id)

    async def delete_group(self, session: AsyncSession, *, group_id: UUID, actor: User) -> None:
        group, membership = await self._require_group_and_membership(session, group_id, actor.id)
        _require_owner(membership)
        await self.groups.delete(session, group)

    async def join_group(self, session: AsyncSession, *, group_id: UUID, actor: User) -> GroupResponse:
        group = await self.groups.get_by_id(session, group_id)
        if group is None:
            raise AppError(code="group_not_found", message="Study group not found", status_code=404)
        existing = await self.memberships.get(session, user_id=actor.id, group_id=group_id)
        if existing is not None:
            raise AppError(
                code="already_a_member",
                message="You are already a member of this group",
                status_code=409,
            )
        await self.memberships.add(
            session,
            GroupMembership(user_id=actor.id, group_id=group.id, role=MembershipRole.MEMBER),
        )
        return await self.get_group(session, group_id=group.id, user_id=actor.id)

    async def leave_group(self, session: AsyncSession, *, group_id: UUID, actor: User) -> None:
        _group, membership = await self._require_group_and_membership(session, group_id, actor.id)
        if membership.role == MembershipRole.OWNER:
            raise AppError(
                code="owner_cannot_leave",
                message="Owners cannot leave a group. Transfer ownership or delete the group.",
                status_code=409,
            )
        await self._release_membership(session, membership, group_id=group_id, user_id=actor.id)

    async def list_members(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
    ) -> list[MemberResponse]:
        await self._require_group_and_membership(session, group_id, actor.id)
        rows = await self.memberships.list_for_group(session, group_id)
        return [
            MemberResponse(
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                university=user.university,
                major=user.major,
                role=membership.role,
                joined_at=membership.joined_at,
            )
            for membership, user in rows
        ]

    async def update_member_role(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        target_user_id: UUID,
        actor: User,
        role: MemberRoleLiteral,
    ) -> MemberResponse:
        _group, actor_membership = await self._require_group_and_membership(
            session, group_id, actor.id
        )
        _require_owner(actor_membership)
        if target_user_id == actor.id:
            raise AppError(
                code="cannot_change_own_role",
                message="You cannot change your own role",
                status_code=409,
            )
        target = await self.memberships.get(session, user_id=target_user_id, group_id=group_id)
        if target is None:
            raise AppError(code="member_not_found", message="Member not found", status_code=404)
        if target.role == MembershipRole.OWNER:
            raise AppError(
                code="cannot_change_owner_role",
                message="Ownership cannot be changed from this endpoint",
                status_code=409,
            )
        target.role = MembershipRole(role)
        await session.flush()
        members = await self.list_members(session, group_id=group_id, actor=actor)
        return next(member for member in members if member.user_id == target_user_id)

    async def remove_member(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        target_user_id: UUID,
        actor: User,
    ) -> None:
        _group, actor_membership = await self._require_group_and_membership(
            session, group_id, actor.id
        )
        _require_owner_or_admin(actor_membership)
        target = await self.memberships.get(session, user_id=target_user_id, group_id=group_id)
        if target is None:
            raise AppError(code="member_not_found", message="Member not found", status_code=404)
        if target.role == MembershipRole.OWNER:
            raise AppError(
                code="cannot_remove_owner",
                message="The group owner cannot be removed",
                status_code=409,
            )
        if target_user_id == actor.id:
            raise AppError(
                code="cannot_remove_self",
                message="Use the leave endpoint to leave a group",
                status_code=409,
            )
        if (
            actor_membership.role == MembershipRole.ADMIN
            and target.role == MembershipRole.ADMIN
        ):
            raise AppError(
                code="forbidden",
                message="Admins cannot remove other admins",
                status_code=403,
            )
        await self._release_membership(
            session, target, group_id=group_id, user_id=target_user_id
        )

    async def _release_membership(
        self,
        session: AsyncSession,
        membership: GroupMembership,
        *,
        group_id: UUID,
        user_id: UUID,
    ) -> None:
        """Remove a membership and clean up what it owned.

        Tasks assigned to a departing member are unassigned rather than
        deleted: the work still needs doing, it just has no owner. Both
        statements run in the request's single transaction, so a failure
        cannot leave a non-member assigned to a task.
        """
        await self.tasks.clear_assignments_for_member(
            session, group_id=group_id, user_id=user_id
        )
        await self.memberships.delete(session, membership)

    async def _require_group_and_membership(
        self,
        session: AsyncSession,
        group_id: UUID,
        user_id: UUID,
    ) -> tuple[StudyGroup, GroupMembership]:
        return await require_group_and_membership(
            session,
            groups=self.groups,
            memberships=self.memberships,
            group_id=group_id,
            user_id=user_id,
        )


def _to_group_response(
    group: StudyGroup,
    member_count: int,
    my_role: MembershipRole | None,
) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        course_code=group.course_code,
        owner_id=group.owner_id,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=member_count,
        my_role=my_role,
    )


group_service = GroupService()
