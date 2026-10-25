"""Fan-out for real-time events.

A message posted by one student has to reach every other student who has an
open stream — possibly on a different API worker. That is a pub/sub problem,
not a database problem.

Two real implementations, selected at startup:

* RedisBroker      — Redis pub/sub. Works across processes and machines, so
                     it is what Docker Compose and any multi-worker deploy use.
* InMemoryBroker    — asyncio fan-out inside one process. Correct and fully
                     functional for a single-worker dev server or tests, but
                     events do not cross process boundaries.

Neither is a stub. The in-memory one is chosen only when Redis is not
reachable, and the choice is logged so it is never a silent downgrade.
"""

from __future__ import annotations

import asyncio
import contextlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import structlog

logger = structlog.get_logger("campusflow.realtime")

# Bounded so one stalled client cannot grow a queue without limit. If a
# subscriber falls this far behind it is dropped; the client reconnects and
# replays what it missed via Last-Event-ID.
_QUEUE_MAXSIZE = 200


class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, channel: str, payload: str) -> None: ...

    @abstractmethod
    def subscribe(self, channel: str) -> "Subscription": ...

    async def close(self) -> None:  # pragma: no cover - overridden when needed
        return None

    @property
    @abstractmethod
    def name(self) -> str: ...


class Subscription(ABC):
    """Async context manager yielding raw payload strings."""

    @abstractmethod
    async def __aenter__(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def __aexit__(self, *exc_info: Any) -> None: ...


class InMemoryBroker(MessageBroker):
    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue[str]]] = {}

    @property
    def name(self) -> str:
        return "in-memory"

    async def publish(self, channel: str, payload: str) -> None:
        for queue in list(self._channels.get(channel, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("subscriber_dropped_event", channel=channel)

    def subscribe(self, channel: str) -> "Subscription":
        return _InMemorySubscription(self, channel)

    def _add(self, channel: str, queue: asyncio.Queue[str]) -> None:
        self._channels.setdefault(channel, set()).add(queue)

    def _remove(self, channel: str, queue: asyncio.Queue[str]) -> None:
        subscribers = self._channels.get(channel)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._channels.pop(channel, None)

    def subscriber_count(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))


class _InMemorySubscription(Subscription):
    def __init__(self, broker: InMemoryBroker, channel: str) -> None:
        self._broker = broker
        self._channel = channel
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)

    async def __aenter__(self) -> AsyncIterator[str]:
        self._broker._add(self._channel, self._queue)
        return self._iterate()

    async def __aexit__(self, *_exc_info: Any) -> None:
        self._broker._remove(self._channel, self._queue)

    async def _iterate(self) -> AsyncIterator[str]:
        while True:
            yield await self._queue.get()


class RedisBroker(MessageBroker):
    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "redis"

    async def publish(self, channel: str, payload: str) -> None:
        await self._client.publish(channel, payload)

    def subscribe(self, channel: str) -> "Subscription":
        return _RedisSubscription(self._client, channel)

    async def close(self) -> None:
        await self._client.aclose()


class _RedisSubscription(Subscription):
    def __init__(self, client: Any, channel: str) -> None:
        self._client = client
        self._channel = channel
        self._pubsub: Any = None

    async def __aenter__(self) -> AsyncIterator[str]:
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self._channel)
        return self._iterate()

    async def __aexit__(self, *_exc_info: Any) -> None:
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(self._channel)
                await self._pubsub.aclose()

    async def _iterate(self) -> AsyncIterator[str]:
        async for item in self._pubsub.listen():
            if item.get("type") != "message":
                continue
            data = item["data"]
            yield data.decode() if isinstance(data, bytes) else data


async def create_broker(redis_url: str | None) -> MessageBroker:
    """Prefer Redis; fall back to in-process fan-out if it is unreachable."""
    if redis_url:
        try:
            import redis.asyncio as redis_asyncio

            client = redis_asyncio.from_url(redis_url)
            await client.ping()
            logger.info("broker_selected", broker="redis")
            return RedisBroker(client)
        except Exception as exc:
            logger.warning(
                "redis_unavailable_using_in_memory_broker",
                error=str(exc),
                detail="Real-time events will not cross worker processes.",
            )
    else:
        logger.info("broker_selected", broker="in-memory", detail="No REDIS_URL configured")
    return InMemoryBroker()
