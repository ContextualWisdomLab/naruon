"""Test-first contracts for the authenticated contextual-orchestrator client."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import httpx
import pytest

from services.contextual_orchestrator_client import (
    ContextualOrchestratorClient,
    ContextualOrchestratorError,
)
from services.email_writing_orchestrator_port import EmailWritingOrchestratorPort
from services.llm_provider_urls import ValidatedLLMProviderBaseURL


MESSAGES = [
    {"role": "system", "content": "Return strict JSON."},
    {"role": "user", "content": "Review this draft."},
]


def _validated(*addresses: str) -> ValidatedLLMProviderBaseURL:
    return ValidatedLLMProviderBaseURL(
        normalized_url="https://orchestrator.example",
        hostname="orchestrator.example",
        port=443,
        addresses=addresses or ("93.184.216.34",),
    )


def _success_payload(*, mode: str = "conduct") -> dict[str, Any]:
    return {
        "id": "chatcmpl-opaque",
        "object": "chat.completion",
        "model": "internal-provider-model-must-not-leak",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"diagnostics":[]}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
        "orchestration": {
            "mode": mode,
            "workflow_run_id": "private-run-id",
            "trace": [
                {
                    "role": "worker",
                    "output": "private model output",
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 3,
                        "total_tokens": 8,
                    },
                },
                {
                    "role": "verifier",
                    "usage": {
                        "prompt_tokens": 6,
                        "completion_tokens": 4,
                        "total_tokens": 10,
                    },
                },
            ],
        },
        "provider_url": "https://provider.example/private",
    }


def _builder(handler):
    transport = httpx.MockTransport(handler)

    def build(_normalized_url: str, _hostname: str, _port: int, _addresses):
        return httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    return build


async def _validator(_value: str | None) -> ValidatedLLMProviderBaseURL:
    return _validated()


@pytest.mark.asyncio
async def test_complete_posts_only_the_fixed_authenticated_contract_and_redacts_trace() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_success_payload())

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(handler),
    )

    completion = await client.complete(MESSAGES, mode="conduct")

    assert completion.as_dict() == {
        "answer": '{"diagnostics":[]}',
        "mode": "conduct",
        "trace": [
            {
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                }
            },
            {
                "usage": {
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "total_tokens": 10,
                }
            },
        ],
    }
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url == httpx.URL(
        "https://orchestrator.example/v1/chat/completions"
    )
    assert request.headers["authorization"] == "Bearer tenant-secret-token"
    payload = json.loads(request.content)
    assert payload == {
        "model": "email-review-v1",
        "messages": MESSAGES,
        "mode": "conduct",
        "include_orchestration_trace": True,
    }
    assert "provider_url" not in completion.as_dict()
    assert "workflow_run_id" not in completion.as_dict()
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body", "expected_code"),
    [
        (401, {"error": {"code": "unauthorized", "message": "secret detail"}}, "orchestrator_unauthorized"),
        (403, {"error": {"code": "forbidden", "message": "secret detail"}}, "orchestrator_unauthorized"),
        (429, {"error": {"code": "rate_limit_exceeded"}}, "orchestrator_rate_limited"),
        (503, {"error": {"code": "concurrency_limit_exceeded"}}, "orchestrator_saturated"),
        (400, {"error": {"code": "invalid_mode", "message": "provider detail"}}, "orchestrator_policy_rejected"),
        (500, {"error": {"code": "internal", "message": "stack trace"}}, "orchestrator_unavailable"),
    ],
)
async def test_http_failures_map_to_stable_redacted_outcomes(
    status_code: int,
    body: dict[str, Any],
    expected_code: str,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(handler),
        max_retries=0,
    )
    with pytest.raises(ContextualOrchestratorError) as captured:
        await client.complete(MESSAGES, mode="route")
    assert captured.value.code == expected_code
    assert str(captured.value) == expected_code
    assert "secret" not in repr(captured.value)
    assert "provider" not in repr(captured.value)


@pytest.mark.asyncio
async def test_transient_statuses_retry_but_unauthorized_does_not() -> None:
    transient_attempts = 0

    async def transient_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal transient_attempts
        transient_attempts += 1
        if transient_attempts < 3:
            return httpx.Response(503, json={"error": {"code": "upstream_unavailable"}})
        return httpx.Response(200, json=_success_payload(mode="route"))

    delays: list[float] = []

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(transient_handler),
        sleeper=sleeper,
        max_retries=2,
    )
    assert (await client.complete(MESSAGES, mode="route")).mode == "route"
    assert transient_attempts == 3
    assert delays == [0.05, 0.1]

    unauthorized_attempts = 0

    async def unauthorized_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal unauthorized_attempts
        unauthorized_attempts += 1
        return httpx.Response(401, json={"error": {"code": "unauthorized"}})

    unauthorized = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(unauthorized_handler),
        sleeper=sleeper,
        max_retries=2,
    )
    with pytest.raises(ContextualOrchestratorError) as captured:
        await unauthorized.complete(MESSAGES, mode="route")
    assert captured.value.code == "orchestrator_unauthorized"
    assert unauthorized_attempts == 1


@pytest.mark.asyncio
async def test_redirects_are_not_followed_and_dns_rebinding_fails_closed() -> None:
    request_count = 0

    async def redirect_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/internal"},
        )

    redirect_client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(redirect_handler),
        max_retries=0,
    )
    with pytest.raises(ContextualOrchestratorError) as captured:
        await redirect_client.complete(MESSAGES, mode="route")
    assert captured.value.code == "orchestrator_policy_rejected"
    assert request_count == 1

    validations = 0

    async def rebinding_validator(_value: str | None) -> ValidatedLLMProviderBaseURL:
        nonlocal validations
        validations += 1
        return _validated(
            "93.184.216.34" if validations == 1 else "93.184.216.35"
        )

    async def success_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_payload(mode="route"))

    rebinding_client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=rebinding_validator,
        client_builder=_builder(success_handler),
        max_retries=0,
    )
    assert (await rebinding_client.complete(MESSAGES, mode="route")).mode == "route"
    with pytest.raises(ContextualOrchestratorError) as rebound:
        await rebinding_client.complete(MESSAGES, mode="route")
    assert rebound.value.code == "orchestrator_policy_rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_body",
    [
        b'{"choices":[],"choices":[],"orchestration":{"mode":"route"}}',
        b'{"choices":[],"orchestration":{"mode":"route"}}',
        b'{"choices":[{"message":{"content":"ok"}}],"orchestration":{"mode":"auto"}}',
        b'[]',
        b'not-json',
    ],
)
async def test_malformed_responses_fail_closed(raw_body: bytes) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw_body)

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(handler),
        max_retries=0,
    )
    with pytest.raises(ContextualOrchestratorError) as captured:
        await client.complete(MESSAGES, mode="route")
    assert captured.value.code == "orchestrator_malformed_response"


@pytest.mark.asyncio
async def test_oversized_body_invalid_messages_cancellation_and_close() -> None:
    async def oversized_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 257)

    oversized = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(oversized_handler),
        max_response_bytes=256,
        max_retries=0,
    )
    with pytest.raises(ContextualOrchestratorError) as body_error:
        await oversized.complete(MESSAGES, mode="route")
    assert body_error.value.code == "orchestrator_malformed_response"

    with pytest.raises(ContextualOrchestratorError) as message_error:
        await oversized.complete(
            [{"role": "user", "content": "ok", "endpoint": "forged"}],
            mode="route",
        )
    assert message_error.value.code == "orchestrator_policy_rejected"

    started = asyncio.Event()

    async def blocked_handler(_request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    cancellable = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(blocked_handler),
        max_retries=0,
    )
    task = asyncio.create_task(cancellable.complete(MESSAGES, mode="route"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await cancellable.aclose()
    with pytest.raises(ContextualOrchestratorError) as closed:
        await cancellable.complete(MESSAGES, mode="route")
    assert closed.value.code == "orchestrator_client_closed"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_transient_failures() -> None:
    attempts = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": {"code": "unavailable"}})

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(handler),
        max_retries=0,
        circuit_failure_threshold=2,
        circuit_open_seconds=30.0,
    )
    for _ in range(2):
        with pytest.raises(ContextualOrchestratorError):
            await client.complete(MESSAGES, mode="route")
    with pytest.raises(ContextualOrchestratorError) as opened:
        await client.complete(MESSAGES, mode="route")
    assert opened.value.code == "orchestrator_unavailable"
    assert attempts == 2


@pytest.mark.asyncio
async def test_port_exposes_async_candidate_sync_judge_shape_and_bounded_lane() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_payload(mode="route"))

    client = ContextualOrchestratorClient(
        base_url="https://orchestrator.example",
        inference_credential="tenant-secret-token",
        model_profile_id="email-review-v1",
        endpoint_validator=_validator,
        client_builder=_builder(handler),
    )
    port = EmailWritingOrchestratorPort(client, judge_capacity=1)

    candidate = await port.complete_candidate(MESSAGES, mode="route")
    assert candidate["answer"] == '{"diagnostics":[]}'
    synchronous = await asyncio.to_thread(port.complete, MESSAGES, mode="route")
    assert synchronous["mode"] == "route"

    entered: list[str] = []
    release = threading.Event()

    def judge(label: str) -> str:
        entered.append(label)
        if label == "first":
            release.wait(timeout=2.0)
        return label

    first = asyncio.create_task(port.run_judge(judge, "first"))
    for _ in range(100):
        if entered:
            break
        await asyncio.sleep(0.001)
    second = asyncio.create_task(port.run_judge(judge, "second"))
    await asyncio.sleep(0.02)
    assert entered == ["first"]
    release.set()
    assert await first == "first"
    assert await second == "second"

    await port.aclose()
    with pytest.raises(RuntimeError, match="judge_lane_closed"):
        await port.run_judge(judge, "closed")



@pytest.mark.asyncio
async def test_cancelled_judge_retains_capacity_until_worker_settles() -> None:
    """Cancellation does not return while its submitted worker still runs."""

    class _PortClient:
        async def aclose(self) -> None:
            return None

    port = EmailWritingOrchestratorPort(_PortClient(), judge_capacity=1)
    started = threading.Event()
    release = threading.Event()

    def blocking_judge() -> str:
        started.set()
        release.wait(timeout=2.0)
        return "settled"

    task = asyncio.create_task(port.run_judge(blocking_judge))
    assert await asyncio.to_thread(started.wait, 1.0)
    task.cancel()
    await asyncio.sleep(0.02)
    returned_before_worker_settled = task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await port.aclose()
    assert returned_before_worker_settled is False
