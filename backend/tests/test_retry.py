"""Tests for the transient provider retry helper."""

import asyncio

import httpx
import openai
import pytest

from services.retry import retry_transient


def _connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", "https://api.test"))


@pytest.mark.asyncio
async def test_returns_result_on_first_success(monkeypatch):
    async def operation():
        return "ok"

    assert await retry_transient(operation) == "ok"


@pytest.mark.asyncio
async def test_retries_transient_error_then_succeeds(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _connection_error()
        return "recovered"

    assert await retry_transient(operation, retries=2) == "recovered"
    assert attempts == 3
    assert len(sleeps) == 2
    # Exponential: second delay window starts at 2x the first base.
    assert sleeps[1] > sleeps[0] * 0.9


@pytest.mark.asyncio
async def test_raises_after_retry_budget_exhausted(monkeypatch):
    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise _connection_error()

    with pytest.raises(openai.APIConnectionError):
        await retry_transient(operation, retries=2)
    assert attempts == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError("bad request shape")

    with pytest.raises(ValueError):
        await retry_transient(operation, retries=5)
    assert attempts == 1


@pytest.mark.asyncio
async def test_custom_retryable_tuple(monkeypatch):
    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    attempts = 0

    class Flaky(Exception):
        pass

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Flaky()
        return "done"

    assert await retry_transient(operation, retryable=(Flaky,)) == "done"
    assert attempts == 2
