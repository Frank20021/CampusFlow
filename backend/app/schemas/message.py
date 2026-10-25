from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

MAX_MESSAGE_LENGTH = 2000


class MessageAuthor(ORMModel):
    id: UUID
    first_name: str
    last_name: str


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message cannot be empty")
        return stripped


class MessageResponse(BaseModel):
    """Identical shape whether it arrives over REST history or the SSE stream.

    Deliberately carries no `can_delete` flag: that depends on the *viewer*,
    and a broadcast payload has many viewers. The client derives it from
    `user_id` plus its own role in the group, and the server re-checks on
    DELETE, so the flag would be advisory anyway.
    """

    id: UUID
    group_id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    author: MessageAuthor | None = None


class MessagePage(BaseModel):
    """Keyset page of history.

    `items` is oldest-first so the client can append directly to the top of
    the transcript. `next_cursor` is the id of the oldest message in this
    page; pass it as `before` to fetch the page before it.
    """

    items: list[MessageResponse]
    has_more: bool
    next_cursor: UUID | None = None
