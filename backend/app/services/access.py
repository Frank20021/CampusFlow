"""Resource-level authorization helpers.

Every group-scoped feature (groups in Phase 1, tasks in Phase 2, chat later)
answers the same question: is this caller a member of this group, and what is
their role? Keeping that in one module means a new feature cannot accidentally
skip the check by forgetting to copy it.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.membership import GroupMembership, MembershipRole
from app.models.study_group import StudyGroup
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository


async def require_group_and_membership(
    session: AsyncSession,
    *,
    groups: GroupRepository,
    memberships: MembershipRepository,
    group_id: UUID,
    user_id: UUID,
) -> tuple[StudyGroup, GroupMembership]:
    group = await groups.get_by_id(session, group_id)
    if group is None:
        raise AppError(code="group_not_found", message="Study group not found", status_code=404)
    membership = await memberships.get(session, user_id=user_id, group_id=group_id)
    if membership is None:
        raise AppError(
            code="not_a_member",
            message="You are not a member of this group",
            status_code=403,
        )
    return group, membership


def require_owner(membership: GroupMembership) -> None:
    if membership.role != MembershipRole.OWNER:
        raise AppError(
            code="forbidden",
            message="Only the group owner can perform this action",
            status_code=403,
        )


def require_owner_or_admin(membership: GroupMembership) -> None:
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise AppError(
            code="forbidden",
            message="Only group owners and admins can perform this action",
            status_code=403,
        )


def is_owner_or_admin(membership: GroupMembership) -> bool:
    return membership.role in {MembershipRole.OWNER, MembershipRole.ADMIN}
