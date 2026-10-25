from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.common import UserPublic
from app.schemas.user import UserUpdateRequest


class UserService:
    def __init__(self, users: UserRepository | None = None) -> None:
        self.users = users or UserRepository()

    async def get_me(self, session: AsyncSession, user_id: UUID) -> User:
        user = await self.users.get_by_id(session, user_id)
        if user is None:
            raise AppError(code="user_not_found", message="User not found", status_code=404)
        return user

    async def update_me(
        self,
        session: AsyncSession,
        user: User,
        payload: UserUpdateRequest,
    ) -> UserPublic:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(user, field, value)
        await session.flush()
        return UserPublic.model_validate(user)


user_service = UserService()
