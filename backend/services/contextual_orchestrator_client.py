"""Authenticated, fail-closed transport to contextual-orchestrator.

The client accepts only a tenant-scoped HTTPS origin and one fixed
``/v1/chat/completions`` path. DNS is resolved through Naruon's canonical
allowlist validator on every completion, the resulting address set is pinned to
the HTTP transport, redirects are disabled, and a later address-set change is
rejected as a possible rebinding event. Returned orchestration evidence is
reduced to token counts; prompts, answers, provider details, URLs, credentials,
workflow identifiers, and trace messages are never retained by this module.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import re
import threading
import time
from typing import Any, Literal, Protocol, TypeAlias, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from services.llm_provider_urls import (
    ValidatedLLMProviderBaseURL,
    build_pinned_https_async_client,
    validate_llm_provider_base_url_details_async,
)

OrchestrationMode = Literal["route", "conduct"]
ChatMessage: TypeAlias = Mapping[str, str]
EndpointValidator: TypeAlias = Callable[
    [str | None], Awaitable[ValidatedLLMProviderBaseURL | None]
]
ClientBuilder: TypeAlias = Callable[
    [str, str, int, tuple[str, ...]], httpx.AsyncClient
]
AsyncSleeper: TypeAlias = Callable[[float], Awaitable[None]]

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_ALLOWED_MESSAGE_ROLES = frozenset({"system", "user", "assistant", "tool"})
_TRANSIENT_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_PROFILE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_MESSAGE_COUNT = 64
_MAX_MESSAGE_CHARS = 200_000
_MAX_TOTAL_MESSAGE_CHARS = 1_000_000
_MAX_SAFE_INTEGER = 2**53 - 1


class _JsonObjectPairsHook(Protocol):
    def __call__(self, pairs: list[tuple[str, Any]]) -> dict[str, Any]: ...


class ContextualOrchestratorError(RuntimeError):
    """Stable, redacted contextual-orchestrator transport failure."""

    def __init__(self, code: str, *, transient: bool = False) -> None:
        """Create an error carrying only a public code and retry classification."""
        super().__init__(code)
        self.code = code
        self.transient = transient

    def __repr__(self) -> str:
        """Return a representation that cannot contain upstream details."""
        return f"ContextualOrchestratorError({self.code!r})"


@dataclass(frozen=True)
class OrchestrationUsageEvidence:
    """Privacy-minimized token evidence for one orchestration step."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def as_dict(self) -> dict[str, int]:
        """Serialize the bounded token counters."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ContextualOrchestratorCompletion:
    """Strict model answer and redacted orchestration evidence."""

    answer: str
    mode: OrchestrationMode
    trace: tuple[OrchestrationUsageEvidence, ...]

    def as_dict(self) -> dict[str, object]:
        """Serialize the completion without provider or workflow metadata."""
        return {
            "answer": self.answer,
            "mode": self.mode,
            "trace": [{"usage": item.as_dict()} for item in self.trace],
        }


def _default_client_builder(
    normalized_url: str,
    hostname: str,
    port: int,
    addresses: tuple[str, ...],
) -> httpx.AsyncClient:
    """Build the canonical redirect-disabled, DNS-pinned HTTPX client."""
    return build_pinned_https_async_client(
        normalized_url,
        hostname,
        port,
        addresses,
    )


def _contains_surrogate(value: str) -> bool:
    """Return whether ``value`` contains a non-scalar Unicode surrogate."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _bounded_secret(value: str, *, maximum: int, code: str) -> str:
    """Normalize one required configuration string without exposing it in errors."""
    if not isinstance(value, str):
        raise ContextualOrchestratorError(code)
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or _contains_surrogate(normalized)
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ContextualOrchestratorError(code)
    return normalized


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate member names."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _bounded_counter(value: Any) -> int:
    """Validate one non-negative JavaScript-safe integer counter."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContextualOrchestratorError("orchestrator_malformed_response")
    if value < 0 or value > _MAX_SAFE_INTEGER:
        raise ContextualOrchestratorError("orchestrator_malformed_response")
    return value


class ContextualOrchestratorClient:
    """Secure per-tenant client for candidate and Judge completions."""

    def __init__(
        self,
        *,
        base_url: str,
        inference_credential: str,
        model_profile_id: str,
        endpoint_validator: EndpointValidator = validate_llm_provider_base_url_details_async,
        client_builder: ClientBuilder = _default_client_builder,
        sleeper: AsyncSleeper = asyncio.sleep,
        max_retries: int = 2,
        max_response_bytes: int = 1_000_000,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 90.0,
        write_timeout_seconds: float = 10.0,
        pool_timeout_seconds: float = 5.0,
        circuit_failure_threshold: int = 3,
        circuit_open_seconds: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a bounded client from already authorized tenant configuration."""
        self._base_url = _bounded_secret(
            base_url,
            maximum=2_048,
            code="orchestrator_policy_rejected",
        )
        self._inference_credential = _bounded_secret(
            inference_credential,
            maximum=16_384,
            code="orchestrator_policy_rejected",
        )
        self._model_profile_id = _bounded_secret(
            model_profile_id,
            maximum=128,
            code="orchestrator_policy_rejected",
        )
        if _PROFILE_IDENTIFIER_RE.fullmatch(self._model_profile_id) is None:
            raise ContextualOrchestratorError("orchestrator_policy_rejected")
        if max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if circuit_failure_threshold <= 0:
            raise ValueError("circuit_failure_threshold must be positive")
        if circuit_open_seconds <= 0:
            raise ValueError("circuit_open_seconds must be positive")

        self._endpoint_validator = endpoint_validator
        self._client_builder = client_builder
        self._sleeper = sleeper
        self._max_retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_open_seconds = circuit_open_seconds
        self._monotonic = monotonic
        self._state_lock = threading.Lock()
        self._closed = False
        self._transient_failure_count = 0
        self._circuit_open_until = 0.0
        self._endpoint_fingerprint: tuple[str, int, tuple[str, ...]] | None = None

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        mode: OrchestrationMode,
    ) -> ContextualOrchestratorCompletion:
        """Submit one strict completion and return privacy-minimized evidence."""
        self._assert_available()
        normalized_messages = self._validate_messages(messages)
        if mode not in {"route", "conduct"}:
            raise ContextualOrchestratorError("orchestrator_policy_rejected")
        endpoint = await self._validated_endpoint()
        payload = {
            "model": self._model_profile_id,
            "messages": normalized_messages,
            "mode": mode,
            "include_orchestration_trace": True,
        }
        headers = {
            "Authorization": f"Bearer {self._inference_credential}",
            "Content-Type": "application/json",
        }

        client = self._client_builder(
            endpoint.normalized_url,
            endpoint.hostname,
            endpoint.port,
            endpoint.addresses,
        )
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    completion = await self._send_once(
                        client,
                        endpoint.normalized_url + _CHAT_COMPLETIONS_PATH,
                        headers,
                        payload,
                    )
                except ContextualOrchestratorError as exc:
                    if not exc.transient or attempt >= self._max_retries:
                        if exc.transient:
                            self._record_transient_failure()
                        raise
                    await self._sleeper(0.05 * (2**attempt))
                except asyncio.CancelledError:
                    raise
                except httpx.TimeoutException as exc:
                    error = ContextualOrchestratorError(
                        "orchestrator_unavailable",
                        transient=True,
                    )
                    if attempt >= self._max_retries:
                        self._record_transient_failure()
                        raise error from exc
                    await self._sleeper(0.05 * (2**attempt))
                except httpx.RequestError as exc:
                    error = ContextualOrchestratorError(
                        "orchestrator_unavailable",
                        transient=True,
                    )
                    if attempt >= self._max_retries:
                        self._record_transient_failure()
                        raise error from exc
                    await self._sleeper(0.05 * (2**attempt))
                else:
                    self._record_success()
                    return completion
        finally:
            await client.aclose()
        raise AssertionError("unreachable completion loop")

    async def aclose(self) -> None:
        """Permanently close this logical tenant client."""
        with self._state_lock:
            self._closed = True

    def _assert_available(self) -> None:
        """Fail before network work when closed or circuit-open."""
        with self._state_lock:
            if self._closed:
                raise ContextualOrchestratorError("orchestrator_client_closed")
            if self._monotonic() < self._circuit_open_until:
                raise ContextualOrchestratorError(
                    "orchestrator_unavailable",
                    transient=True,
                )

    async def _validated_endpoint(self) -> ValidatedLLMProviderBaseURL:
        """Resolve, pin, and bind the configured HTTPS origin."""
        try:
            validated = await self._endpoint_validator(self._base_url)
        except (ValueError, OSError) as exc:
            raise ContextualOrchestratorError(
                "orchestrator_policy_rejected"
            ) from exc
        if validated is None:
            raise ContextualOrchestratorError("orchestrator_policy_rejected")

        parsed = urlsplit(validated.normalized_url)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ContextualOrchestratorError("orchestrator_policy_rejected")
        addresses = tuple(sorted(set(validated.addresses)))
        if not addresses:
            raise ContextualOrchestratorError("orchestrator_policy_rejected")
        fingerprint = (validated.hostname, validated.port, addresses)
        with self._state_lock:
            if self._endpoint_fingerprint is None:
                self._endpoint_fingerprint = fingerprint
            elif self._endpoint_fingerprint != fingerprint:
                raise ContextualOrchestratorError("orchestrator_policy_rejected")
        normalized_origin = urlunsplit(
            (parsed.scheme.lower(), parsed.netloc, "", "", "")
        )
        return ValidatedLLMProviderBaseURL(
            normalized_url=normalized_origin,
            hostname=validated.hostname,
            port=validated.port,
            addresses=addresses,
        )

    def _validate_messages(
        self,
        messages: Sequence[ChatMessage],
    ) -> list[dict[str, str]]:
        """Validate a bounded OpenAI-compatible message array without coercion."""
        if (
            isinstance(messages, (str, bytes))
            or not isinstance(messages, Sequence)
            or not messages
            or len(messages) > _MAX_MESSAGE_COUNT
        ):
            raise ContextualOrchestratorError("orchestrator_policy_rejected")
        normalized: list[dict[str, str]] = []
        total_characters = 0
        for message in messages:
            if not isinstance(message, Mapping) or set(message) != {"role", "content"}:
                raise ContextualOrchestratorError("orchestrator_policy_rejected")
            role = message.get("role")
            content = message.get("content")
            if (
                not isinstance(role, str)
                or role not in _ALLOWED_MESSAGE_ROLES
                or not isinstance(content, str)
                or len(content) > _MAX_MESSAGE_CHARS
                or _contains_surrogate(content)
            ):
                raise ContextualOrchestratorError("orchestrator_policy_rejected")
            total_characters += len(content)
            if total_characters > _MAX_TOTAL_MESSAGE_CHARS:
                raise ContextualOrchestratorError("orchestrator_policy_rejected")
            normalized.append({"role": role, "content": content})
        return normalized

    async def _send_once(
        self,
        client: httpx.AsyncClient,
        endpoint_url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
    ) -> ContextualOrchestratorCompletion:
        """Execute one bounded HTTP request without following redirects."""
        async with client.stream(
            "POST",
            endpoint_url,
            json=payload,
            headers=headers,
            timeout=self._timeout,
            follow_redirects=False,
        ) as response:
            body = await self._read_bounded_body(response)
            if response.is_redirect:
                raise ContextualOrchestratorError("orchestrator_policy_rejected")
            if response.status_code >= 400:
                raise self._http_error(response.status_code, body)
            return self._parse_completion(body)

    async def _read_bounded_body(self, response: httpx.Response) -> bytes:
        """Read at most the configured response-byte budget."""
        chunks: list[bytes] = []
        observed = 0
        async for chunk in response.aiter_bytes():
            observed += len(chunk)
            if observed > self._max_response_bytes:
                raise ContextualOrchestratorError(
                    "orchestrator_malformed_response"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _http_error(self, status_code: int, body: bytes) -> ContextualOrchestratorError:
        """Map an HTTP failure to one stable public outcome."""
        upstream_code = self._safe_upstream_error_code(body)
        if status_code in {401, 403}:
            code = "orchestrator_unauthorized"
        elif status_code == 429:
            code = "orchestrator_rate_limited"
        elif status_code == 503 and upstream_code == "concurrency_limit_exceeded":
            code = "orchestrator_saturated"
        elif status_code >= 500 or status_code in {408, 409, 425}:
            code = "orchestrator_unavailable"
        else:
            code = "orchestrator_policy_rejected"
        return ContextualOrchestratorError(
            code,
            transient=status_code in _TRANSIENT_STATUS_CODES,
        )

    def _safe_upstream_error_code(self, body: bytes) -> str | None:
        """Read only a bounded upstream error code, discarding all other fields."""
        try:
            document = self._strict_json(body)
        except ContextualOrchestratorError:
            return None
        error = document.get("error")
        if not isinstance(error, dict):
            return None
        code = error.get("code")
        if not isinstance(code, str) or len(code) > 128:
            return None
        return code

    def _strict_json(self, body: bytes) -> dict[str, Any]:
        """Decode one duplicate-key-free UTF-8 JSON object."""
        try:
            text = body.decode("utf-8", errors="strict")
            value = json.loads(
                text,
                object_pairs_hook=cast(_JsonObjectPairsHook, _strict_object_pairs),
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    ValueError("non_finite_json_number")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ContextualOrchestratorError(
                "orchestrator_malformed_response"
            ) from exc
        if not isinstance(value, dict):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        return value

    def _parse_completion(self, body: bytes) -> ContextualOrchestratorCompletion:
        """Parse the strict answer and retain only per-step usage evidence."""
        document = self._strict_json(body)
        choices = document.get("choices")
        orchestration = document.get("orchestration")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        answer = message.get("content")
        if not isinstance(answer, str) or _contains_surrogate(answer):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        if not isinstance(orchestration, dict):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        mode = orchestration.get("mode")
        if mode not in {"route", "conduct"}:
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        raw_trace = orchestration.get("trace")
        if not isinstance(raw_trace, list):
            raise ContextualOrchestratorError("orchestrator_malformed_response")
        trace: list[OrchestrationUsageEvidence] = []
        for step in raw_trace:
            if not isinstance(step, dict):
                raise ContextualOrchestratorError(
                    "orchestrator_malformed_response"
                )
            usage = step.get("usage")
            if not isinstance(usage, dict):
                raise ContextualOrchestratorError(
                    "orchestrator_malformed_response"
                )
            trace.append(
                OrchestrationUsageEvidence(
                    prompt_tokens=_bounded_counter(usage.get("prompt_tokens")),
                    completion_tokens=_bounded_counter(
                        usage.get("completion_tokens")
                    ),
                    total_tokens=_bounded_counter(usage.get("total_tokens")),
                )
            )
        return ContextualOrchestratorCompletion(
            answer=answer,
            mode=cast(OrchestrationMode, mode),
            trace=tuple(trace),
        )

    def _record_transient_failure(self) -> None:
        """Advance the circuit breaker after one exhausted transient call."""
        with self._state_lock:
            self._transient_failure_count += 1
            if self._transient_failure_count >= self._circuit_failure_threshold:
                self._circuit_open_until = self._monotonic() + self._circuit_open_seconds

    def _record_success(self) -> None:
        """Close the circuit after a successful completion."""
        with self._state_lock:
            self._transient_failure_count = 0
            self._circuit_open_until = 0.0
