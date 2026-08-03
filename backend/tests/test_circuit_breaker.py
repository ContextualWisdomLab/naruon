"""Tests for the provider circuit breaker."""

import asyncio

import pytest

from services.circuit_breaker import CircuitBreaker, CircuitOpenError


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _failing(exc=RuntimeError("provider down")):
    async def operation():
        raise exc

    return operation


def _succeeding(value="ok"):
    async def operation():
        return value

    return operation


@pytest.mark.asyncio
async def test_closed_circuit_passes_result_through():
    breaker = CircuitBreaker(clock=_Clock())
    assert await breaker.call("p", _succeeding()) == "ok"


@pytest.mark.asyncio
async def test_opens_after_threshold_and_fails_fast():
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30, clock=clock)

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call("p", _failing())

    # Now open: rejects without invoking the operation.
    calls = 0

    async def counting():
        nonlocal calls
        calls += 1
        return "x"

    with pytest.raises(CircuitOpenError) as exc_info:
        await breaker.call("p", counting)
    assert calls == 0
    assert exc_info.value.retry_after_seconds > 0


@pytest.mark.asyncio
async def test_half_open_probe_closes_on_success():
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=clock)

    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())
    clock.now = 11.0  # past cooldown -> half-open probe allowed

    assert await breaker.call("p", _succeeding("recovered")) == "recovered"
    # Fully closed again.
    assert await breaker.call("p", _succeeding()) == "ok"


@pytest.mark.asyncio
async def test_half_open_probe_failure_reopens():
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=clock)

    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())
    clock.now = 11.0

    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())  # probe fails -> reopen

    clock.now = 12.0  # still within the fresh cooldown
    with pytest.raises(CircuitOpenError):
        await breaker.call("p", _succeeding())


@pytest.mark.asyncio
async def test_half_open_rejects_second_probe_while_first_in_flight():
    """Only one half-open probe is admitted at a time: a concurrent call that
    arrives while the single probe is still awaiting fails fast rather than
    piling a second request onto a provider that may still be down."""
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=clock)

    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())
    clock.now = 11.0  # past cooldown -> the next call is the lone half-open probe

    release = asyncio.Event()

    async def slow_probe():
        await release.wait()
        return "recovered"

    probe = asyncio.create_task(breaker.call("p", slow_probe))
    await asyncio.sleep(0)  # let the probe start and claim the in-flight slot

    # A second call while the probe is in flight is rejected fast.
    with pytest.raises(CircuitOpenError):
        await breaker.call("p", _succeeding())

    release.set()
    assert await probe == "recovered"


@pytest.mark.asyncio
async def test_keys_are_isolated():
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=clock)

    with pytest.raises(RuntimeError):
        await breaker.call("down", _failing())
    with pytest.raises(CircuitOpenError):
        await breaker.call("down", _succeeding())

    # A different provider key is unaffected.
    assert await breaker.call("up", _succeeding()) == "ok"


@pytest.mark.asyncio
async def test_success_resets_failure_streak():
    clock = _Clock()
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=10, clock=clock)

    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())
    assert await breaker.call("p", _succeeding()) == "ok"
    with pytest.raises(RuntimeError):
        await breaker.call("p", _failing())
    # Streak was reset, so still closed.
    assert await breaker.call("p", _succeeding()) == "ok"
