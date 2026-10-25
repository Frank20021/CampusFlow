from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.membership import MembershipRole
from app.schemas.common import ORMModel

GroupFilter = Literal["all", "mine"]
MemberRoleLiteral = Literal["admin", "member"]


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    course_code: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be blank")
        return stripped

    @field_validator("description", "course_code")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    course_code: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be blank")
        return stripped

    @field_validator("description", "course_code")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MemberRoleUpdateRequest(BaseModel):
    role: MemberRoleLiteral


class GroupResponse(ORMModel):
    id: UUID
    name: str
    description: str | None
    course_code: str | None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    member_count: int
    my_role: MembershipRole | None = None


class MemberResponse(ORMModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    university: str | None
    major: str | None
    role: MembershipRole
    joined_at: datetime
