"""Development seed script.

This is the only supported way to create demo data. The API never hard-codes
users or groups. Run from the backend directory after migrations:

    python -m scripts.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.membership import GroupMembership, MembershipRole
from app.models.study_group import StudyGroup
from app.models.user import User

DEMO_USERS = [
    {
        "email": "ada@university.edu",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": "CampusFlow1",
        "university": "Analytical University",
        "major": "Mathematics",
    },
    {
        "email": "alan@university.edu",
        "first_name": "Alan",
        "last_name": "Turing",
        "password": "CampusFlow1",
        "university": "Analytical University",
        "major": "Computer Science",
    },
]


async def seed() -> None:
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to seed the production database.")

    engine = create_async_engine(settings.async_database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        existing = await session.scalar(select(User).where(User.email == DEMO_USERS[0]["email"]))
        if existing is not None:
            print("Seed data already present. Nothing to do.")
            await engine.dispose()
            return

        users: list[User] = []
        for spec in DEMO_USERS:
            user = User(
                first_name=spec["first_name"],
                last_name=spec["last_name"],
                email=spec["email"],
                password_hash=hash_password(spec["password"]),
                university=spec["university"],
                major=spec["major"],
            )
            session.add(user)
            users.append(user)
        await session.flush()

        group = StudyGroup(
            name="CS 101 Study Circle",
            description="Weekly problem sets and exam review for intro CS.",
            course_code="CS101",
            owner_id=users[0].id,
        )
        session.add(group)
        await session.flush()
        session.add(
            GroupMembership(user_id=users[0].id, group_id=group.id, role=MembershipRole.OWNER)
        )
        session.add(
            GroupMembership(user_id=users[1].id, group_id=group.id, role=MembershipRole.MEMBER)
        )
        await session.commit()
        print("Seeded demo users ada@university.edu and alan@university.edu (password: CampusFlow1).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
