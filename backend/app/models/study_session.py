import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RsvpStatus(str, enum.Enum):
    GOING = "going"
    MAYBE = "maybe"
    DECLINED = "declined"


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        # "What is coming up for this group" is the dominant read, and it is
        # always a range scan ordered by time.
        Index("ix_study_sessions_group_id_start_time", "group_id", "start_time"),
        # The database refuses a backwards session even if a bug bypasses the
        # Pydantic validator. Constraints that matter belong in both places.
        CheckConstraint("end_time > start_time", name="ck_study_sessions_end_after_start"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    group_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("study_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    # timestamptz throughout: the instant is stored in UTC and rendered in
    # each viewer's own zone, so a session created by a student abroad shows
    # at the right local time for everyone.
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SessionRsvp(Base):
    __tablename__ = "session_rsvps"
    __table_args__ = (
        # One answer per person per session. The unique constraint is what
        # makes the upsert in the service safe under a double-click.
        UniqueConstraint("session_id", "user_id", name="uq_session_rsvps_session_user"),
        Index("ix_session_rsvps_session_id", "session_id"),
        Index("ix_session_rsvps_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RsvpStatus] = mapped_column(
        Enum(
            RsvpStatus,
            name="rsvp_status",
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    responded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
