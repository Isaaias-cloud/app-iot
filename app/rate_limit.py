"""Rate limiting básico en memoria para proteger el endpoint de login."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allowed(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            return len(attempts) < self.max_attempts

    def record_failure(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            attempts.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
