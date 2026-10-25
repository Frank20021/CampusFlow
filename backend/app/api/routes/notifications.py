"""Personal inbox: REST history plus one Server-Sent Events stream.

The stream is per user, not per group. Authorization is "this token belongs
to this user" — there is no membership check, because the rows themselves
are already scoped to `user_id`.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, Pagination, StreamingUserId
from app.core.exceptions import AppError
from app.db.session import get_session_factory
from app.realtime import events
from app.realtime.registry import get_broker
from app.repositories import user_repository
from app.schemas.common import Paginated
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notification import notification_service

logger = structlog.get_logger("campusflow.notifications")

HEARTBEAT_SECONDS = 20.0

router = APIRouter()


@router.get("", response_model=Paginated[NotificationResponse])
async def list_notifications(
    current_user: CurrentUser,
    session: DbSession,
    pagination: Pagination,
    unread_only: Annotated[bool, Query()] = False,
) -> Paginated[NotificationResponse]:
    limit, offset = pagination
    return await notification_service.list_notifications(
        session,
        actor=current_user,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: CurrentUser,
    session: DbSession,
) -> UnreadCountResponse:
    return await notification_service.unread_count(session, actor=current_user)


@router.post("/read-all", response_model=UnreadCountResponse)
async def mark_all_read(
    current_user: CurrentUser,
    session: DbSession,
) -> UnreadCountResponse:
    return await notification_service.mark_all_read(session, actor=current_user)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> NotificationResponse:
    return await notification_service.mark_read(
        session, notification_id=notification_id, actor=current_user
    )


def _frame(event: str, data: dict, *, event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


async def _drain(source: AsyncIterator[str], queue: asyncio.Queue[str]) -> None:
    async for payload in source:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("notification_stream_queue_full")


async def _event_stream(
    *, user_id: UUID, last_event_id: UUID | None
) -> AsyncIterator[str]:
    broker = get_broker()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    async with broker.subscribe(events.user_channel(user_id)) as source:
        pump = asyncio.create_task(_drain(source, queue))
        try:
            replayed: set[str] = set()
            if last_event_id is not None:
                factory = get_session_factory()
                async with factory() as session:
                    missed = await notification_service.replay_since(
                        session, user_id=user_id, last_event_id=last_event_id
                    )
                for item in missed:
                    replayed.add(str(item.id))
                    yield _frame(
                        events.NOTIFICATION_CREATED,
                        item.model_dump(mode="json"),
                        event_id=str(item.id),
                    )

            yield _frame("ready", {"user_id": str(user_id), "transport": broker.name})

            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield _frame(events.PING, {})
                    continue

                envelope = json.loads(raw)
                name = envelope["event"]
                data = envelope["data"]
                if name == events.NOTIFICATION_CREATED:
                    item_id = str(data["id"])
                    if item_id in replayed:
                        replayed.discard(item_id)
                        continue
                    yield _frame(name, data, event_id=item_id)
                else:
                    yield _frame(name, data)
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump


@router.get("/stream")
async def stream_notifications(
    user_id: StreamingUserId,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Live inbox. Authorize now, then hold no database connection."""
    factory = get_session_factory()
    async with factory() as session:
        user = await user_repository.get_by_id(session, user_id)
        if user is None:
            raise AppError(
                code="not_authenticated", message="Authentication required", status_code=401
            )

    cursor: UUID | None = None
    if last_event_id:
        with contextlib.suppress(ValueError):
            cursor = UUID(last_event_id)

    logger.info("notification_stream_opened", user_id=str(user_id))
    return StreamingResponse(
        _event_stream(user_id=user_id, last_event_id=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
