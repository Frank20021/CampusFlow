"""In-app notifications.

Chat messages are deliberately excluded. That conversation already has a
history and a live stream; writing one inbox row per message would bury the
events a student actually missed while they were elsewhere.

Writes commit before they are published, for the same reason as chat: a
subscriber must never render a row that a later rollback erases.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.realtime import events
from app.realtime.registry import get_broker
from app.repositories import (
    membership_repository,
    notification_repository,
)
from app.repositories.membership import MembershipRepository
from app.repositories.notification import NotificationRepository
from app.schemas.common import Paginated
from app.schemas.notification import (
    NotificationActor,
    NotificationResponse,
    UnreadCountResponse,
)

MAX_REPLAY = 100


def _now() -> datetime:
    return datetime.now(UTC)


def _actor_name(actor: User) -> str:
    return f"{actor.first_name} {actor.last_name}".strip()


def to_response(notification: Notification, actor: User | None) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        actor_id=notification.actor_id,
        group_id=notification.group_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        href=notification.href,
        entity_id=notification.entity_id,
        read_at=notification.read_at,
        created_at=notification.created_at,
        actor=NotificationActor.model_validate(actor) if actor is not None else None,
    )


def encode_event(event: str, data: dict) -> str:
    return json.dumps({"event": event, "data": data})


@dataclass(frozen=True)
class NotificationDraft:
    user_id: UUID
    actor: User
    group_id: UUID
    type: NotificationType
    title: str
    body: str
    href: str
    entity_id: UUID


class NotificationService:
    def __init__(
        self,
        *,
        notifications: NotificationRepository,
        memberships: MembershipRepository,
    ) -> None:
        self.notifications = notifications
        self.memberships = memberships

    async def list_notifications(
        self,
        session: AsyncSession,
        *,
        actor: User,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> Paginated[NotificationResponse]:
        rows, total = await self.notifications.list_for_user(
            session,
            user_id=actor.id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        items = [to_response(notification, actor_user) for notification, actor_user in rows]
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def unread_count(
        self, session: AsyncSession, *, actor: User
    ) -> UnreadCountResponse:
        return UnreadCountResponse(
            unread=await self.notifications.unread_count(session, user_id=actor.id)
        )

    async def mark_read(
        self, session: AsyncSession, *, notification_id: UUID, actor: User
    ) -> NotificationResponse:
        notification = await self.notifications.get_by_id(session, notification_id)
        if notification is None or notification.user_id != actor.id:
            # Same 404 either way so a guessed id does not confirm that a
            # notification exists for someone else.
            raise AppError(
                code="notification_not_found",
                message="Notification not found",
                status_code=404,
            )
        await self.notifications.mark_read(session, notification, when=_now())
        row = await self.notifications.get_with_actor(session, notification.id)
        if row is None:
            return to_response(notification, None)
        return to_response(row[0], row[1])

    async def mark_all_read(self, session: AsyncSession, *, actor: User) -> UnreadCountResponse:
        await self.notifications.mark_all_read(session, user_id=actor.id, when=_now())
        return UnreadCountResponse(unread=0)

    async def replay_since(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        last_event_id: UUID,
    ) -> list[NotificationResponse]:
        anchor = await self.notifications.get_by_id(session, last_event_id)
        if anchor is None or anchor.user_id != user_id:
            return []
        rows = await self.notifications.list_after(
            session,
            user_id=user_id,
            after=(anchor.created_at, anchor.id),
            limit=MAX_REPLAY,
        )
        return [to_response(notification, actor) for notification, actor in rows]

    async def notify_task_assigned(
        self,
        session: AsyncSession,
        *,
        actor: User,
        assignee_id: UUID,
        group_id: UUID,
        group_name: str,
        task_id: UUID,
        task_title: str,
    ) -> None:
        if assignee_id == actor.id:
            return
        name = _actor_name(actor)
        await self._emit(
            session,
            [
                NotificationDraft(
                    user_id=assignee_id,
                    actor=actor,
                    group_id=group_id,
                    type=NotificationType.TASK_ASSIGNED,
                    title="Task assigned to you",
                    body=f'{name} assigned you “{task_title}” in {group_name}',
                    href=f"/app/groups/{group_id}/tasks",
                    entity_id=task_id,
                )
            ],
        )

    async def notify_session_created(
        self,
        session: AsyncSession,
        *,
        actor: User,
        group_id: UUID,
        group_name: str,
        session_id: UUID,
        session_title: str,
    ) -> None:
        drafts = await self._drafts_for_group(
            session,
            actor=actor,
            group_id=group_id,
            type=NotificationType.SESSION_CREATED,
            title="New study session",
            body=f'{_actor_name(actor)} scheduled “{session_title}” in {group_name}',
            href=f"/app/groups/{group_id}/sessions",
            entity_id=session_id,
        )
        await self._emit(session, drafts)

    async def notify_resource_shared(
        self,
        session: AsyncSession,
        *,
        actor: User,
        group_id: UUID,
        group_name: str,
        resource_id: UUID,
        resource_title: str,
    ) -> None:
        drafts = await self._drafts_for_group(
            session,
            actor=actor,
            group_id=group_id,
            type=NotificationType.RESOURCE_SHARED,
            title="Resource shared",
            body=f'{_actor_name(actor)} shared “{resource_title}” in {group_name}',
            href=f"/app/groups/{group_id}/resources",
            entity_id=resource_id,
        )
        await self._emit(session, drafts)

    async def notify_rsvp_updated(
        self,
        session: AsyncSession,
        *,
        actor: User,
        organizer_id: UUID,
        group_id: UUID,
        group_name: str,
        session_id: UUID,
        session_title: str,
        status: str,
    ) -> None:
        if organizer_id == actor.id:
            return
        name = _actor_name(actor)
        await self._emit(
            session,
            [
                NotificationDraft(
                    user_id=organizer_id,
                    actor=actor,
                    group_id=group_id,
                    type=NotificationType.RSVP_UPDATED,
                    title="RSVP updated",
                    body=f'{name} is {status} for “{session_title}” in {group_name}',
                    href=f"/app/groups/{group_id}/sessions",
                    entity_id=session_id,
                )
            ],
        )

    async def _drafts_for_group(
        self,
        session: AsyncSession,
        *,
        actor: User,
        group_id: UUID,
        type: NotificationType,
        title: str,
        body: str,
        href: str,
        entity_id: UUID,
    ) -> list[NotificationDraft]:
        user_ids = await self.memberships.list_user_ids(session, group_id)
        return [
            NotificationDraft(
                user_id=user_id,
                actor=actor,
                group_id=group_id,
                type=type,
                title=title,
                body=body,
                href=href,
                entity_id=entity_id,
            )
            for user_id in user_ids
            if user_id != actor.id
        ]

    async def _emit(self, session: AsyncSession, drafts: list[NotificationDraft]) -> None:
        if not drafts:
            return
        rows = [
            Notification(
                user_id=draft.user_id,
                actor_id=draft.actor.id,
                group_id=draft.group_id,
                type=draft.type,
                title=draft.title,
                body=draft.body,
                href=draft.href,
                entity_id=draft.entity_id,
            )
            for draft in drafts
        ]
        await self.notifications.add_many(session, rows)
        await session.commit()

        broker = get_broker()
        for row, draft in zip(rows, drafts, strict=True):
            payload = to_response(row, draft.actor)
            await broker.publish(
                events.user_channel(row.user_id),
                encode_event(
                    events.NOTIFICATION_CREATED, payload.model_dump(mode="json")
                ),
            )


notification_service = NotificationService(
    notifications=notification_repository,
    memberships=membership_repository,
)
