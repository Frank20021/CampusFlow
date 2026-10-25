from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.study_session import RsvpStatus
from app.schemas.common import ORMModel

# A study session longer than this is almost certainly a typo in the year or
# an unset end time, and it would distort every calendar view it lands in.
MAX_DURATION = timedelta(hours=24)


class SessionUser(ORMModel):
    id: UUID
    first_name: str
    last_name: str
    email: str


class SessionAttendee(BaseModel):
    user: SessionUser
    status: RsvpStatus
    responded_at: datetime


class RsvpCounts(BaseModel):
    going: int = 0
    maybe: int = 0
    declined: int = 0


def validate_window(start: datetime | None, end: datetime | None) -> None:
    if start is None or end is None:
        return
    if end <= start:
        raise ValueError("End time must be after the start time")
    if end - start > MAX_DURATION:
        raise ValueError("A session cannot run longer than 24 hours")


class SessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_window(self) -> "SessionCreateRequest":
        validate_window(self.start_time, self.end_time)
        return self

    @model_validator(mode="after")
    def strip_text(self) -> "SessionCreateRequest":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Title cannot be empty")
        self.description = self.description.strip() if self.description else None
        self.location = self.location.strip() if self.location else None
        return self


class SessionUpdateRequest(BaseModel):
    """Partial update. Times are validated against the stored session in the
    service, since a request may move only one edge of the window."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    start_time: datetime | None = None
    end_time: datetime | None = None


class SessionResponse(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    creator: SessionUser | None = None
    rsvp_counts: RsvpCounts = Field(default_factory=RsvpCounts)
    my_rsvp: RsvpStatus | None = None
    can_manage: bool = False


class MySessionResponse(SessionResponse):
    group_name: str


class RsvpRequest(BaseModel):
    status: RsvpStatus
