import time
import uuid
from collections import defaultdict

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.exceptions import error_body

logger = structlog.get_logger("campusflow.request")
_AUTH_PATHS = {"/api/auth/login", "/api/auth/register"}


class RequestContextMiddleware:
    """ASGI middleware for request IDs and latency logs.

    Chosen: raw ASGI instead of Starlette BaseHTTPMiddleware. The latter
    creates a child task that is incompatible with asyncpg (event-loop
    mismatch). Alternative: HTTPX-style pure ASGI is the standard fix.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header(scope, b"x-request-id") or str(uuid.uuid4())
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "http_request",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=duration_ms,
            )


class InMemoryRateLimitMiddleware:
    """Fixed-window limiter for register/login. Not cluster-safe; Redis comes later."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        path = scope.get("path", "")
        if path not in _AUTH_PATHS or settings.environment.lower() == "test":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        host = client[0] if client else "unknown"
        key = f"{host}:{path}"
        now = time.monotonic()
        window = settings.auth_rate_limit_window_seconds
        hits = [stamp for stamp in self._hits[key] if stamp > now - window]
        self._hits[key] = hits

        if len(hits) >= settings.auth_rate_limit_max:
            request_id = scope.get("state", {}).get("request_id")
            body = error_body(
                code="rate_limited",
                message="Too many attempts. Please wait and try again.",
                request_id=request_id,
            )
            await _send_json(send, 429, body, extra_headers=[(b"retry-after", str(window).encode())])
            return

        self._hits[key].append(now)
        await self.app(scope, receive, send)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


async def _send_json(
    send: Send,
    status: int,
    payload: dict,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    import json

    raw = json.dumps(payload).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(raw)).encode()),
        *(extra_headers or []),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": raw})
