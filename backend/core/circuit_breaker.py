from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.exceptions import CircuitOpenError


@dataclass
class CircuitBreaker:
    provider: str
    failure_threshold: int
    cooldown_seconds: float
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    def _reset_if_cooled(self) -> None:
        if self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._opened_at = None
                self._failures = 0

    def check(self) -> None:
        """Raise CircuitOpenError if the circuit is open. Call before making a provider request."""
        self._reset_if_cooled()
        if self._opened_at is not None:
            raise CircuitOpenError(self.provider)

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    @property
    def is_open(self) -> bool:
        self._reset_if_cooled()
        return self._opened_at is not None
