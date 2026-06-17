from __future__ import annotations

import time
from typing import Callable, Dict, Optional, TypeVar

T = TypeVar('T')


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 20.0,
        half_open_after: float = 10.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_after = half_open_after
        self.failures = 0
        self.state = 'CLOSED'
        self.opened_at: Optional[float] = None
        self.last_failure_at: Optional[float] = None

    def allow_request(self) -> bool:
        if self.state == 'CLOSED':
            return True
        if self.state == 'OPEN':
            if self.opened_at is not None and (time.time() - self.opened_at) >= self.recovery_timeout:
                self.state = 'HALF_OPEN'
                return True
            return False
        if self.state == 'HALF_OPEN':
            return True
        return True

    def mark_success(self) -> None:
        self.failures = 0
        self.state = 'CLOSED'
        self.opened_at = None
        self.last_failure_at = None

    def mark_failure(self) -> None:
        now = time.time()
        self.last_failure_at = now
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = 'OPEN'
            self.opened_at = now

    async def call(self, func: Callable[..., T], *args: object, **kwargs: object) -> T:
        if not self.allow_request():
            raise RuntimeError(f'Circuit breaker {self.name} is open')
        try:
            result = await func(*args, **kwargs)
            self.mark_success()
            return result
        except Exception:
            self.mark_failure()
            raise
