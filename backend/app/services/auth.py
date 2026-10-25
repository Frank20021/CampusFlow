from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import UserPublic


class AuthService:
    def __init__(self, users: UserRepository | None = None) -> None:
        self.users = users or UserRepository()

    async def register(self, session: AsyncSession, payload: RegisterRequest) -> TokenResponse:
        existing = await self.users.get_by_email(session, payload.email)
        if existing is not None:
            raise AppError(
                code="email_taken",
                message="An account with this email already exists",
                status_code=409,
            )

        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            university=payload.university,
            major=payload.major,
        )
        user = await self.users.add(session, user)
        return self._token_response(user)

    async def login(self, session: AsyncSession, payload: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(session, payload.email)
        # Same message for missing user and bad password so we do not leak
        # whether an email is registered.
        if user is None or not verify_password(payload.password, user.password_hash):
            raise AppError(
                code="invalid_credentials",
                message="Email or password is incorrect",
                status_code=401,
            )
        return self._token_response(user)

    def _token_response(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id=user.id),
            user=UserPublic.model_validate(user),
        )


auth_service = AuthService()
