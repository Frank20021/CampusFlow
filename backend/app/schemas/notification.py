from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.notification import NotificationType
from app.schemas.common import ORMModel


class NotificationActor(ORMModel):
    id: UUID
    first_name: str
    last_name: str


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    actor_id: UUID | None
    group_id: UUID | None
    type: NotificationType
    title: str
    body: str
    href: str
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime
    actor: NotificationActor | None = None


class UnreadCountResponse(BaseModel):
    unread: int
