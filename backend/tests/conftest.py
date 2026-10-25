from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ["DATABASE_URL"] = "postgresql://campusflow:campusflow@localhost:5432/campusflow_test"
os.environ["JWT_SECRET"] = "test-secret-key-which-is-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"

from alembic import command
from alembic.config import Config

import app.db.session as db_session_module
from app.core.config import clear_settings_cache, get_settings
from app.db.session import get_db, reset_engine
from app.main import create_app
from app.realtime.broker import InMemoryBroker
from app.realtime.registry import set_broker
from app.services.message import message_service

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_migrations() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def settings():
    clear_settings_cache()
    return get_settings()


@pytest.fixture(scope="session")
def migrated_database(settings) -> None:
    _run_migrations()


@pytest.fixture(autouse=True)
async def isolated_process_state() -> AsyncGenerator[None, None]:
    """Reset the globals that outlive a single test.

    The SSE route deliberately bypasses the `get_db` override and uses the
    application's own engine, so that engine must not survive into the next
    test's event loop — asyncpg connections are bound to the loop that opened
    them. The broker and the message throttle are process-wide for the same
    reason and get a clean slate too.
    """
    reset_engine()
    set_broker(InMemoryBroker())
    message_service.throttle.reset()
    yield
    engine = db_session_module._engine
    if engine is not None:
        await engine.dispose()
    reset_engine()
    set_broker(None)


@pytest.fixture
async def db_engine(settings, migrated_database):
    engine = create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async with db_engine.connect() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE notifications, session_rsvps, study_sessions, resources, "
                "messages, tasks, group_memberships, study_groups, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await connection.commit()

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    application.dependency_overrides.clear()


@pytest.fixture
def register_payload() -> Callable[..., dict]:
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": f"ada{counter['n']}@university.edu",
            "password": "Secret123",
            "university": "Analytical University",
            "major": "Mathematics",
        }
        payload.update(overrides)
        return payload

    return _make


@pytest.fixture
async def auth_header(client: AsyncClient, register_payload) -> Callable[..., Awaitable[tuple[dict, dict]]]:
    async def _auth(**overrides) -> tuple[dict, dict]:
        response = await client.post("/api/auth/register", json=register_payload(**overrides))
        assert response.status_code == 201, response.text
        body = response.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    return _auth
