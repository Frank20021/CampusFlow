from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import UserPublic
from app.schemas.user import UserUpdateRequest
from app.services.user import user_service

router = APIRouter()


@router.get("/me", response_model=UserPublic)
async def read_me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UserUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> UserPublic:
    return await user_service.update_me(session, current_user, payload)
