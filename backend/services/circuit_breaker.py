"""In-process circuit breaker for provider calls.

Complements the transient retry: retries handle blips; the breaker stops
hammering a provider that is hard-down, failing fast instead of stacking
timeout latency onto every user request.

ponytail: in-process state only — each worker/replica trips independently.
Upgrade to a shared store if per-replica probing ever matters at fleet scale.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN_SECONDS = 30.0


class CircuitOpenError(Exception):
    """Raised immediately while a provider's circuit is open."""

    def __init__(self, key: str, retry_after_seconds: float):
        super().__init__(
            f"Circuit open for {key}; retry in {retry_after_seconds:.0f}s"
        )
        self.key = key
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None
    half_open_probe_in_flight: bool = False


@dataclass
class CircuitBreaker:
    """Per-key (e.g. provider base URL) three-state breaker.

    closed -> open after ``failure_threshold`` consecutive failures;
    open -> half-open after ``cooldown_seconds`` (one probe allowed);
    half-open -> closed on probe success, back to open on probe failure.
    """

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    clock: Callable[[], float] = time.monotonic
    _states: dict[str, _CircuitState] = field(default_factory=dict)

    def _state(self, key: str) -> _CircuitState:
        return self._states.setdefault(key, _CircuitState())

    async def call(
        self,
        key: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        state = self._state(key)

        if state.opened_at is not None:
            elapsed = self.clock() - state.opened_at
            if elapsed < self.cooldown_seconds:
                raise CircuitOpenError(key, self.cooldown_seconds - elapsed)
            if state.half_open_probe_in_flight:
                raise CircuitOpenError(key, self.cooldown_seconds)
            state.half_open_probe_in_flight = True

        try:
            result = await operation()
        except Exception:
            if state.opened_at is not None:
                # Half-open probe failed: reopen for a fresh cooldown.
                state.opened_at = self.clock()
                state.half_open_probe_in_flight = False
                logger.warning("Circuit for %s reopened after failed probe", key)
            else:
                state.consecutive_failures += 1
                if state.consecutive_failures >= self.failure_threshold:
                    state.opened_at = self.clock()
                    state.half_open_probe_in_flight = False
                    logger.warning(
                        "Circuit for %s opened after %d consecutive failures",
                        key,
                        state.consecutive_failures,
                    )
            raise

        state.consecutive_failures = 0
        state.opened_at = None
        state.half_open_probe_in_flight = False
        return result


# Shared instance for LLM/embedding provider call sites.
provider_circuit_breaker = CircuitBreaker()
