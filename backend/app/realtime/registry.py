"""Process-wide broker handle.

The broker is created once during application startup and reused by both the
message service (publish) and the SSE route (subscribe). If startup never ran
— for example an ASGI test client that skips lifespan — an in-process broker
is created on demand so behaviour stays correct rather than crashing.
"""

from app.realtime.broker import InMemoryBroker, MessageBroker

_broker: MessageBroker | None = None


def set_broker(broker: MessageBroker | None) -> None:
    global _broker
    _broker = broker


def get_broker() -> MessageBroker:
    global _broker
    if _broker is None:
        _broker = InMemoryBroker()
    return _broker
