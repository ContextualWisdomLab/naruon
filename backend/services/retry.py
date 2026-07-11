"""Bounded retry for transient LLM/embedding provider failures.

Stdlib-only (no new dependency): retries ONLY transient provider errors —
connection drops, timeouts, rate limits, and 5xx — with exponential backoff and
jitter. Auth, bad-request, and other 4xx errors fail immediately so callers keep
their existing fail-closed behavior.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from secrets import randbelow
from typing import TypeVar

import openai

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 429 and 5xx are worth one more attempt; 4xx auth/validation errors are not.
TRANSIENT_OPENAI_ERRORS: tuple[type[Exception], ...] = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

DEFAULT_PROVIDER_RETRIES = 2
DEFAULT_BASE_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 8.0
JITTER_RESOLUTION = 1_000_000


def _jitter_seconds(max_seconds: float) -> float:
    if max_seconds <= 0:
        return 0.0
    return (randbelow(JITTER_RESOLUTION + 1) / JITTER_RESOLUTION) * max_seconds


async def retry_transient(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = DEFAULT_PROVIDER_RETRIES,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    retryable: tuple[type[Exception], ...] = TRANSIENT_OPENAI_ERRORS,
    operation_name: str = "provider call",
) -> T:
    """Run ``operation``, retrying transient failures with backoff + jitter.

    ``retries`` is the number of retries after the first attempt (so the
    operation runs at most ``retries + 1`` times). Non-retryable exceptions
    propagate immediately; the last transient failure propagates unchanged
    after the budget is exhausted.
    """
    attempt = 0
    while True:
        try:
            return await operation()
        except retryable as exc:
            if attempt >= retries:
                raise
            delay = min(base_delay_seconds * (2**attempt), MAX_DELAY_SECONDS)
            delay += _jitter_seconds(delay / 2)
            attempt += 1
            logger.warning(
                "Transient %s failure (attempt %d/%d), retrying in %.2fs: %s",
                operation_name,
                attempt,
                retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
