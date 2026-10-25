"""Group chat: REST history plus one Server-Sent Events stream.

Why SSE and not WebSockets: sending a message is an ordinary authenticated
write that wants validation, persistence, authorization and throttling, so it
stays a POST. Only delivery is push, and that is one-directional. SSE gets
reconnection and gap recovery (`Last-Event-ID`) from the protocol itself.
WebSockets would earn their keep for typing indicators or presence, which is
not this phase.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, StreamingUserId
from app.core.exceptions import AppError
from app.db.session import get_session_factory
from app.realtime import events
from app.realtime.registry import get_broker
from app.repositories import user_repository
from app.schemas.message import MessageCreateRequest, MessagePage, MessageResponse
from app.services.message import message_service

logger = structlog.get_logger("campusflow.messages")

# Long enough to stay cheap, short enough that proxies and load balancers with
# the common 60s idle timeout never close a quiet chat.
HEARTBEAT_SECONDS = 20.0

group_messages_router = APIRouter()
messages_router = APIRouter()


@group_messages_router.post(
    "/{group_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    group_id: UUID,
    payload: MessageCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MessageResponse:
    return await message_service.post_message(
        session, group_id=group_id, actor=current_user, payload=payload
    )


@group_messages_router.get("/{group_id}/messages", response_model=MessagePage)
async def list_messages(
    group_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    before: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> MessagePage:
    """Newest page by default; pass `before` (a message id) to walk backwards."""
    return await message_service.list_messages(
        session, group_id=group_id, actor=current_user, before=before, limit=limit
    )


@messages_router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await message_service.delete_message(session, message_id=message_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _frame(event: str, data: dict, *, event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


async def _drain(source: AsyncIterator[str], queue: asyncio.Queue[str]) -> None:
    """Move broker payloads into a queue the stream loop can time out on.

    Reading the broker directly would mean cancelling an in-flight `__anext__`
    on every heartbeat, which can leave an async generator in a broken state.
    Cancelling `queue.get()` is safe, so the timeout lives here instead.
    """
    async for payload in source:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("stream_queue_full_dropping_event")


async def _event_stream(
    *, group_id: UUID, last_event_id: UUID | None
) -> AsyncIterator[str]:
    broker = get_broker()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    async with broker.subscribe(events.group_channel(group_id)) as source:
        pump = asyncio.create_task(_drain(source, queue))
        try:
            # Subscribe first, then replay. Doing it the other way round would
            # drop anything posted between the catch-up query and the
            # subscription. This way that window produces a duplicate instead,
            # which `replayed` filters out.
            replayed: set[str] = set()
            if last_event_id is not None:
                factory = get_session_factory()
                async with factory() as session:
                    missed = await message_service.replay_since(
                        session, group_id=group_id, last_event_id=last_event_id
                    )
                for message in missed:
                    replayed.add(str(message.id))
                    yield _frame(
                        events.MESSAGE_CREATED,
                        message.model_dump(mode="json"),
                        event_id=str(message.id),
                    )

            yield _frame("ready", {"group_id": str(group_id), "transport": broker.name})

            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield _frame(events.PING, {})
                    continue

                envelope = json.loads(raw)
                name = envelope["event"]
                data = envelope["data"]

                if name == events.MESSAGE_CREATED:
                    message_id = str(data["id"])
                    if message_id in replayed:
                        replayed.discard(message_id)
                        continue
                    # Only creations carry an id: Last-Event-ID is resumed by
                    # looking the message up, and a deleted row cannot anchor
                    # anything.
                    yield _frame(name, data, event_id=message_id)
                else:
                    yield _frame(name, data)
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump


@group_messages_router.get("/{group_id}/stream")
async def stream_group_events(
    group_id: UUID,
    user_id: StreamingUserId,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Live group events. Authorize now, then hold no database connection."""
    factory = get_session_factory()
    async with factory() as session:
        user = await user_repository.get_by_id(session, user_id)
        if user is None:
            raise AppError(
                code="not_authenticated", message="Authentication required", status_code=401
            )
        await message_service.authorize_stream(session, group_id=group_id, user_id=user_id)

    cursor: UUID | None = None
    if last_event_id:
        with contextlib.suppress(ValueError):
            cursor = UUID(last_event_id)

    logger.info("stream_opened", group_id=str(group_id), user_id=str(user_id))

    return StreamingResponse(
        _event_stream(group_id=group_id, last_event_id=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Tells nginx not to buffer the response, which would otherwise
            # hold events until the buffer fills and defeat the whole point.
            "X-Accel-Buffering": "no",
        },
    )
