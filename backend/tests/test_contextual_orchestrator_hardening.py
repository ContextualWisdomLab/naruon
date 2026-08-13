"""Security and lifecycle regressions for the email-writing orchestration boundary."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from fastapi import HTTPException
import httpx
import pytest

from api import tenant_config
from services.contextual_orchestrator_client import (
    ContextualOrchestratorClient,
    ContextualOrchestratorError,
)
from services.email_writing_orchestrator_port import EmailWritingOrchestratorPort
from services.llm_provider_urls import ValidatedLLMProviderBaseURL

_MESSAGES = (
    {"role": "system", "content": "Return strict JSON."},
    {"role": "user", "content": "Review this draft."},
)


def _validated(
    normalized_url: str = "https://orchestrator.example",
) -> ValidatedLLMProviderBaseURL:
    """Return one deterministic globally routed test endpoint."""
    return ValidatedLLMProviderBaseURL(
        normalized_url=normalized_url,
        hostname="orchestrator.example",
        port=443,
        addresses=("93.184.216.34",),
    )


async def _endpoint_validator(
    _value: str | None,
) -> ValidatedLLMProviderBaseURL:
    """Resolve the deterministic endpoint used by transport tests."""
    return _validated()


def _client_builder(handler: Any):
    """Build a redirect-disabled HTTPX client around one mock handler."""
    transport = httpx.MockTransport(handler)

    def build(
        _normalized_url: str,
        _hostname: str,
        _port: int,
        _addresses: tuple[str, ...],
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    return build


def _completion_payload(
    *,
    mode: str = "route",
    trace_count: int = 1,
    metadata: object | None = None,
) -> dict[str, object]:
    """Build one syntactically valid orchestrator response fixture."""
    payload: dict[str, object] = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"diagnostics":[]}',
                }
            }
        ],
        "orchestration": {
            "mode": mode,
            "trace": [
                {
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    }
                }
                for _ in range(trace_count)
            ],
        },
    }
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


@pytest.mark.asyncio
async def test_response_mode_must_match_the_requested_orchestration_mode() -> None:
    """A route request must not accept evidence labelled as conduct, or vice versa."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion_payload(mode="conduct"))

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_endpoint_validator,
        client_builder=_client_builder(handler),
        max_retries=0,
    )
    with pytest.raises(ContextualOrchestratorError) as captured:
        await client.complete(_MESSAGES, mode="route")
    assert captured.value.code == "orchestrator_malformed_response"


@pytest.mark.asyncio
async def test_response_json_depth_and_trace_cardinality_are_bounded() -> None:
    """Bounded bytes do not substitute for bounded JSON work or trace cardinality."""
    nested: object = "leaf"
    for _ in range(40):
        nested = {"next": nested}

    responses = iter(
        (
            _completion_payload(metadata=nested),
            _completion_payload(trace_count=65),
        )
    )

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_endpoint_validator,
        client_builder=_client_builder(handler),
        max_retries=0,
    )
    for _ in range(2):
        with pytest.raises(ContextualOrchestratorError) as captured:
            await client.complete(_MESSAGES, mode="route")
        assert captured.value.code == "orchestrator_malformed_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "normalized_url",
    (
        "http://orchestrator.example",
        "https://orchestrator.example/v1",
        "https://orchestrator.example?tenant=forged",
    ),
)
async def test_configuration_accepts_only_an_https_origin(
    monkeypatch: pytest.MonkeyPatch,
    normalized_url: str,
) -> None:
    """Configuration cannot persist a downgraded or path-bearing endpoint."""

    async def validator(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL:
        return _validated(normalized_url)

    monkeypatch.setattr(
        tenant_config,
        "validate_llm_provider_base_url_details_async",
        validator,
    )
    with pytest.raises(HTTPException) as captured:
        await tenant_config._validated_orchestrator_url(normalized_url)
    assert captured.value.status_code == 400
    assert captured.value.detail == "Invalid email-writing orchestrator configuration"
    assert "orchestrator.example" not in str(captured.value)


@pytest.mark.asyncio
async def test_waiting_judge_fails_stably_when_close_starts() -> None:
    """A waiter must not submit work to an executor after shutdown has begun."""

    class _PortClient:
        async def aclose(self) -> None:
            return None

    port = EmailWritingOrchestratorPort(_PortClient(), judge_capacity=1)
    first_started = threading.Event()
    release_first = threading.Event()

    def first_operation() -> str:
        first_started.set()
        release_first.wait(timeout=2.0)
        return "first"

    first = asyncio.create_task(port.run_judge(first_operation))
    assert await asyncio.to_thread(first_started.wait, 1.0)
    second = asyncio.create_task(port.run_judge(lambda: "second"))
    await asyncio.sleep(0)
    close = asyncio.create_task(port.aclose())
    await asyncio.sleep(0.02)
    release_first.set()

    assert await first == "first"
    with pytest.raises(RuntimeError, match="judge_lane_closed"):
        await second
    await close


@pytest.mark.asyncio
async def test_cancelled_judge_preserves_cancellation_when_worker_later_fails() -> None:
    """A worker exception after cancellation must not replace CancelledError."""

    class _PortClient:
        async def aclose(self) -> None:
            return None

    port = EmailWritingOrchestratorPort(_PortClient(), judge_capacity=1)
    started = threading.Event()
    release = threading.Event()

    def failing_operation() -> None:
        started.set()
        release.wait(timeout=2.0)
        raise ValueError("private worker detail")

    task = asyncio.create_task(port.run_judge(failing_operation))
    assert await asyncio.to_thread(started.wait, 1.0)
    task.cancel()
    await asyncio.sleep(0.02)
    assert task.done() is False
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await port.aclose()
