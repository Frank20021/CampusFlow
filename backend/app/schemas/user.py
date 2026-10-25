from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UserPublic


class UserUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    university: str | None = Field(default=None, max_length=200)
    major: str | None = Field(default=None, max_length=200)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be blank")
        return stripped

    @field_validator("university", "major")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UserResponse(UserPublic):
    pass
