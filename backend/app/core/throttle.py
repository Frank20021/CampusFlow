import time
from collections import defaultdict, deque

from app.core.exceptions import AppError


class SlidingWindowThrottle:
    """Per-key sliding-window limiter.

    Used for message posting, which is the easiest endpoint in the product to
    spam. Keyed by user id rather than IP, because a logged-in abuser is the
    realistic case and IP is shared on campus networks.

    Chosen: in-process, like the auth rate limiter, so Phase 3 has a real
    limit today. Alternative: Redis INCR with expiry, which is accurate
    across workers — that is the upgrade when the broker moves to Redis in a
    multi-worker deploy. Tradeoff: this resets per process and each worker
    enforces its own budget.
    """

    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, message: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self.max_events:
            raise AppError(code="rate_limited", message=message, status_code=429)

        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()
