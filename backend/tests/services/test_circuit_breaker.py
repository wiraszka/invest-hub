from __future__ import annotations

import time

import pytest

from core.circuit_breaker import CircuitBreaker
from core.exceptions import CircuitOpenError


@pytest.fixture
def breaker() -> CircuitBreaker:
    return CircuitBreaker(provider="test", failure_threshold=3, cooldown_seconds=60.0)


class TestCircuitBreaker:
    def test_allows_calls_when_closed(self, breaker: CircuitBreaker) -> None:
        breaker.check()  # should not raise

    def test_opens_after_threshold_failures(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open

    def test_raises_when_open(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()

        with pytest.raises(CircuitOpenError) as exc_info:
            breaker.check()

        assert exc_info.value.provider == "test"

    def test_resets_on_success(self, breaker: CircuitBreaker) -> None:
        for _ in range(2):
            breaker.record_failure()

        breaker.record_success()

        assert not breaker.is_open
        breaker.check()  # should not raise

    def test_half_opens_after_cooldown(self, breaker: CircuitBreaker) -> None:
        fast_breaker = CircuitBreaker(
            provider="test", failure_threshold=1, cooldown_seconds=0.01
        )
        fast_breaker.record_failure()

        assert fast_breaker.is_open

        time.sleep(0.02)

        assert not fast_breaker.is_open
        fast_breaker.check()  # should not raise after cooldown
