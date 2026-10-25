from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User

MessageRow = tuple[Message, User]


class MessageRepository:
    """Keyset (cursor) pagination, not OFFSET.

    Chat inserts constantly at the newest end. With OFFSET, a message posted
    while a student scrolls back shifts every later page by one and they see
    a duplicate or a gap. Comparing on (created_at, id) is stable regardless
    of inserts, and matches the composite index exactly.
    """

    async def get_by_id(self, session: AsyncSession, message_id: UUID) -> Message | None:
        return await session.get(Message, message_id)

    async def add(self, session: AsyncSession, message: Message) -> Message:
        session.add(message)
        await session.flush()
        return message

    async def delete(self, session: AsyncSession, message: Message) -> None:
        await session.delete(message)
        await session.flush()

    async def get_with_author(self, session: AsyncSession, message_id: UUID) -> MessageRow | None:
        stmt = (
            select(Message, User)
            .join(User, User.id == Message.user_id)
            .where(Message.id == message_id)
        )
        row = (await session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def list_page(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        before: tuple[datetime, UUID] | None,
        limit: int,
    ) -> tuple[list[MessageRow], bool]:
        """Newest-first page, walking backwards from `before`."""
        stmt = (
            select(Message, User)
            .join(User, User.id == Message.user_id)
            .where(Message.group_id == group_id)
        )
        if before is not None:
            stmt = stmt.where(tuple_(Message.created_at, Message.id) < before)

        # Fetch one extra row to learn whether an older page exists without
        # running a second COUNT query over the whole history.
        stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
        rows = (await session.execute(stmt)).all()

        has_more = len(rows) > limit
        page = rows[:limit]
        return [(row[0], row[1]) for row in page], has_more

    async def list_after(
        self,
        session: AsyncSession,
        *,
        group_id: UUID,
        after: tuple[datetime, UUID],
        limit: int,
    ) -> list[MessageRow]:
        """Messages newer than a cursor, oldest-first.

        Used to replay what a client missed while its stream was down.
        """
        stmt = (
            select(Message, User)
            .join(User, User.id == Message.user_id)
            .where(Message.group_id == group_id)
            .where(tuple_(Message.created_at, Message.id) > after)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
