"""Group chat.

Ordering guarantee worth stating: a message is broadcast only *after* its
transaction commits. Publishing inside the transaction would let a subscriber
render a message that a later rollback erases, and no reload would ever bring
it back. So these two methods commit explicitly instead of relying on the
request-scoped commit in `get_db`.
"""

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.throttle import SlidingWindowThrottle
from app.models.message import Message
from app.models.user import User
from app.realtime import events
from app.realtime.registry import get_broker
from app.repositories import (
    group_repository,
    membership_repository,
    message_repository,
)
from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.message import MessageRepository
from app.schemas.message import (
    MessageAuthor,
    MessageCreateRequest,
    MessagePage,
    MessageResponse,
)
from app.services import access

MAX_PAGE_SIZE = 100
# Replay is capped: a client offline for hours should reload history from
# scratch rather than receive thousands of events in one burst.
MAX_REPLAY = 100


def to_response(message: Message, author: User | None) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        group_id=message.group_id,
        user_id=message.user_id,
        content=message.content,
        created_at=message.created_at,
        author=MessageAuthor.model_validate(author) if author is not None else None,
    )


def encode_event(event: str, data: dict) -> str:
    return json.dumps({"event": event, "data": data})


class MessageService:
    def __init__(
        self,
        *,
        groups: GroupRepository,
        memberships: MembershipRepository,
        messages: MessageRepository,
    ) -> None:
        self.groups = groups
        self.memberships = memberships
        self.messages = messages
        self.throttle = SlidingWindowThrottle(max_events=20, window_seconds=10.0)

    async def _require_membership(
        self, session: AsyncSession, *, group_id: UUID, user_id: UUID
    ):
        return await access.require_group_and_membership(
            session,
            groups=self.groups,
            memberships=self.memberships,
            group_id=group_id,
            user_id=user_id,
        )

    async def authorize_stream(
        self, session: AsyncSession, *, group_id: UUID, user_id: UUID
    ) -> None:
        """Membership check for the SSE route, which holds no session itself."""
        await self._require_membership(session, group_id=group_id, user_id=user_id)

    async def post_message(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        payload: MessageCreateRequest,
    ) -> MessageResponse:
        await self._require_membership(session, group_id=group_id, user_id=actor.id)
        self.throttle.check(
            f"messages:{actor.id}",
            message="You are sending messages too quickly. Wait a moment and try again.",
        )

        message = Message(
            group_id=group_id,
            user_id=actor.id,
            content=payload.content,
        )
        await self.messages.add(session, message)
        await session.commit()

        response = to_response(message, actor)
        await get_broker().publish(
            events.group_channel(group_id),
            encode_event(events.MESSAGE_CREATED, response.model_dump(mode="json")),
        )
        return response

    async def list_messages(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        actor: User,
        before: UUID | None,
        limit: int,
    ) -> MessagePage:
        await self._require_membership(session, group_id=group_id, user_id=actor.id)

        cursor = None
        if before is not None:
            anchor = await self.messages.get_by_id(session, before)
            if anchor is None or anchor.group_id != group_id:
                raise AppError(
                    code="invalid_cursor",
                    message="That pagination cursor is not valid for this group",
                    status_code=400,
                )
            cursor = (anchor.created_at, anchor.id)

        rows, has_more = await self.messages.list_page(
            session, group_id=group_id, before=cursor, limit=min(limit, MAX_PAGE_SIZE)
        )

        # The query walks backwards from newest; the transcript reads forwards.
        rows.reverse()
        items = [to_response(message, author) for message, author in rows]
        return MessagePage(
            items=items,
            has_more=has_more,
            next_cursor=items[0].id if items and has_more else None,
        )

    async def replay_since(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        last_event_id: UUID,
    ) -> list[MessageResponse]:
        """Messages posted after `last_event_id`, for stream gap recovery."""
        anchor = await self.messages.get_by_id(session, last_event_id)
        if anchor is None or anchor.group_id != group_id:
            return []
        rows = await self.messages.list_after(
            session,
            group_id=group_id,
            after=(anchor.created_at, anchor.id),
            limit=MAX_REPLAY,
        )
        return [to_response(message, author) for message, author in rows]

    async def delete_message(
        self, session: AsyncSession, *, message_id: UUID, actor: User
    ) -> None:
        """Authors delete their own; owners and admins moderate anyone's."""
        message = await self.messages.get_by_id(session, message_id)
        if message is None:
            raise AppError(code="message_not_found", message="Message not found", status_code=404)

        _, membership = await self._require_membership(
            session, group_id=message.group_id, user_id=actor.id
        )
        if message.user_id != actor.id and not access.is_owner_or_admin(membership):
            raise AppError(
                code="forbidden",
                message="You can only delete your own messages",
                status_code=403,
            )

        group_id = message.group_id
        await self.messages.delete(session, message)
        await session.commit()

        await get_broker().publish(
            events.group_channel(group_id),
            encode_event(
                events.MESSAGE_DELETED,
                {"id": str(message_id), "group_id": str(group_id)},
            ),
        )


message_service = MessageService(
    groups=group_repository,
    memberships=membership_repository,
    messages=message_repository,
)
