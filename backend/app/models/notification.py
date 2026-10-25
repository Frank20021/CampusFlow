import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, enum.Enum):
    TASK_ASSIGNED = "task_assigned"
    SESSION_CREATED = "session_created"
    RESOURCE_SHARED = "resource_shared"
    RSVP_UPDATED = "rsvp_updated"


class Notification(Base):
    """A durable inbox row, not a transient event.

    SSE delivers these while the student is online. The table is what they
    still have after a refresh, which is why chat messages are *not* stored
    here: that conversation already has a history and a live stream.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_created_at_id", "user_id", "created_at", "id"),
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("study_groups.id", ondelete="CASCADE"),
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    href: Mapped[str] = mapped_column(String(400), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
