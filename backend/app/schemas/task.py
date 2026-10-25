from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.task import TaskPriority, TaskStatus
from app.schemas.common import ORMModel


class TaskUser(ORMModel):
    id: UUID
    first_name: str
    last_name: str
    email: str


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    assigned_to: UUID | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskUpdateRequest(BaseModel):
    """Partial update.

    Every field is optional, and `model_dump(exclude_unset=True)` in the
    service distinguishes "not sent" from "explicitly set to null". That is
    what lets a client clear an assignee or a due date.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    assigned_to: UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskResponse(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    description: str | None
    assigned_to: UUID | None
    created_by: UUID
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime
    assignee: TaskUser | None = None
    creator: TaskUser | None = None
    can_delete: bool = False


class MyTaskResponse(TaskResponse):
    """A task on the dashboard needs its group name for context."""

    group_name: str
