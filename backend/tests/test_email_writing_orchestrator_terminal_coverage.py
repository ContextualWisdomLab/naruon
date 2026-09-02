"""Terminal branch coverage for the Task 5 orchestration boundary."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, cast

from fastapi import HTTPException
import httpx
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, inspect

from api.auth import AuthContext
from api import email_writing_orchestrator_config as config_api
from services import contextual_orchestrator_client as client_module
from services.contextual_orchestrator_client import (
    ContextualOrchestratorClient,
    ContextualOrchestratorCompletion,
    ContextualOrchestratorError,
)
from services.email_writing_orchestrator_port import EmailWritingOrchestratorPort
from services.llm_provider_urls import ValidatedLLMProviderBaseURL
from services import tenant_config_scope as scope_module


_MESSAGES = (
    {"role": "system", "content": "Return strict JSON."},
    {"role": "user", "content": "Review this draft."},
)


def _validated(
    *,
    normalized_url: str = "https://orchestrator.example",
    addresses: tuple[str, ...] = ("93.184.216.34",),
) -> ValidatedLLMProviderBaseURL:
    """Build one deterministic endpoint validation result."""
    return ValidatedLLMProviderBaseURL(
        normalized_url=normalized_url,
        hostname="orchestrator.example",
        port=443,
        addresses=addresses,
    )


async def _valid_endpoint(
    _value: str | None,
) -> ValidatedLLMProviderBaseURL:
    """Return one deterministic valid endpoint."""
    return _validated()


def _payload(
    *,
    mode: str = "route",
    trace: object | None = None,
) -> dict[str, object]:
    """Build one strict success response."""
    return {
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
            "trace": (
                [
                    {
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        }
                    }
                ]
                if trace is None
                else trace
            ),
        },
    }


def _builder(handler: Any):
    """Build a redirect-disabled mock HTTP client factory."""
    transport = httpx.MockTransport(handler)

    def build(
        _normalized_url: str,
        _hostname: str,
        _port: int,
        _addresses: tuple[str, ...],
    ) -> httpx.AsyncClient:
        """Build one mock client."""
        return httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    return build


def _client(**overrides: Any) -> ContextualOrchestratorClient:
    """Build a client with deterministic defaults."""
    values: dict[str, Any] = {
        "base_url": "https://orchestrator.example",
        "inference_credential": "tenant-secret-token",
        "model_profile_id": "email-review-v1",
        "endpoint_validator": _valid_endpoint,
        "client_builder": _builder(
            lambda _request: httpx.Response(
                200,
                json=_payload(),
            )
        ),
        "max_retries": 0,
    }
    values.update(overrides)
    return ContextualOrchestratorClient(**values)


def test_private_validation_helpers_cover_all_terminal_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise deterministic helpers without making a network request."""
    sentinel = cast(httpx.AsyncClient, object())

    def pinned_builder(
        normalized_url: str,
        hostname: str,
        port: int,
        addresses: tuple[str, ...],
    ) -> httpx.AsyncClient:
        assert (
            normalized_url,
            hostname,
            port,
            addresses,
        ) == (
            "https://orchestrator.example",
            "orchestrator.example",
            443,
            ("93.184.216.34",),
        )
        return sentinel

    monkeypatch.setattr(
        client_module,
        "build_pinned_https_async_client",
        pinned_builder,
    )
    assert (
        client_module._default_client_builder(
            "https://orchestrator.example",
            "orchestrator.example",
            443,
            ("93.184.216.34",),
        )
        is sentinel
    )
    assert client_module._contains_surrogate("ordinary") is False
    assert client_module._contains_surrogate("\ud800") is True
    assert (
        client_module._bounded_secret(
            "  value  ",
            maximum=16,
            code="invalid",
        )
        == "value"
    )

    for value in (
        cast(Any, 7),
        "",
        "x" * 17,
        "\ud800",
        "line\nbreak",
        "\x7f",
    ):
        with pytest.raises(ContextualOrchestratorError, match="invalid"):
            client_module._bounded_secret(
                value,
                maximum=16,
                code="invalid",
            )

    assert client_module._strict_object_pairs([("a", 1)]) == {"a": 1}
    with pytest.raises(ValueError, match="duplicate_json_key"):
        client_module._strict_object_pairs([("a", 1), ("a", 2)])

    assert client_module._bounded_counter(0) == 0
    assert client_module._bounded_counter(2**53 - 1) == 2**53 - 1
    for value in (True, 1.0, -1, 2**53):
        with pytest.raises(
            ContextualOrchestratorError,
            match="orchestrator_malformed_response",
        ):
            client_module._bounded_counter(value)

    client_module._validate_json_structure(
        {"array": [1, "ordinary"], "flag": True}
    )
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_malformed_response",
    ):
        client_module._validate_json_structure({"bad": "\ud800"})

    monkeypatch.setattr(client_module, "_MAX_JSON_NODES", 2)
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_malformed_response",
    ):
        client_module._validate_json_structure([1, 2, 3])


@pytest.mark.parametrize(
    "overrides",
    (
        {"model_profile_id": "invalid profile"},
        {"max_retries": -1},
        {"max_retries": 6},
        {"max_response_bytes": 0},
        {"circuit_failure_threshold": 0},
        {"circuit_open_seconds": 0},
    ),
)
def test_constructor_rejects_invalid_configuration(
    overrides: dict[str, object],
) -> None:
    """Reject invalid client bounds before allocating transport resources."""
    with pytest.raises(
        (ContextualOrchestratorError, ValueError),
    ):
        _client(**overrides)


@pytest.mark.asyncio
async def test_invalid_mode_and_unreachable_loop_are_fail_closed() -> None:
    """Reject an unsupported mode and prove the loop terminal is guarded."""
    client = _client()
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_policy_rejected",
    ):
        await client.complete(_MESSAGES, mode=cast(Any, "auto"))

    client._max_retries = -1
    with pytest.raises(AssertionError, match="unreachable completion loop"):
        await client.complete(_MESSAGES, mode="route")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    (httpx.ConnectTimeout, httpx.ConnectError),
)
async def test_transport_exceptions_retry_and_exhaust(
    error_type: type[httpx.RequestError],
) -> None:
    """Retry transient HTTPX failures and return one stable public code."""
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise error_type("private transport detail", request=request)

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    client = _client(
        client_builder=_builder(handler),
        sleeper=sleeper,
        max_retries=1,
    )
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_unavailable",
    ) as captured:
        await client.complete(_MESSAGES, mode="route")
    assert captured.value.transient is True
    assert attempts == 2
    assert delays == [0.05]


@pytest.mark.asyncio
@pytest.mark.parametrize("raised", (ValueError, OSError))
async def test_endpoint_validation_errors_are_redacted(
    raised: type[Exception],
) -> None:
    """Normalize endpoint resolution failures to the policy code."""

    async def validator(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL:
        raise raised("private resolver detail")

    client = _client(endpoint_validator=validator)
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_policy_rejected",
    ):
        await client._validated_endpoint()


@pytest.mark.asyncio
async def test_endpoint_validation_rejects_absent_invalid_and_empty_results() -> None:
    """Accept only one bare HTTPS origin with at least one pinned address."""

    async def absent(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL | None:
        return None

    client = _client(endpoint_validator=absent)
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_policy_rejected",
    ):
        await client._validated_endpoint()

    invalid_urls = (
        "http://orchestrator.example",
        "https://user@orchestrator.example",
        "https://user:pass@orchestrator.example",
        "https://orchestrator.example/path",
        "https://orchestrator.example?query=1",
        "https://orchestrator.example#fragment",
        "https:///",
    )
    for invalid_url in invalid_urls:

        async def invalid(
            _value: str | None,
            *,
            candidate: str = invalid_url,
        ) -> ValidatedLLMProviderBaseURL:
            return _validated(normalized_url=candidate)

        client = _client(endpoint_validator=invalid)
        with pytest.raises(
            ContextualOrchestratorError,
            match="orchestrator_policy_rejected",
        ):
            await client._validated_endpoint()

    async def no_addresses(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL:
        return _validated(addresses=())

    client = _client(endpoint_validator=no_addresses)
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_policy_rejected",
    ):
        await client._validated_endpoint()

    async def duplicates(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL:
        return _validated(
            addresses=(
                "93.184.216.35",
                "93.184.216.34",
                "93.184.216.34",
            )
        )

    client = _client(endpoint_validator=duplicates)
    result = await client._validated_endpoint()
    assert result.addresses == ("93.184.216.34", "93.184.216.35")


def test_message_validation_covers_all_rejection_branches() -> None:
    """Reject malformed messages, hostile Unicode, and exceeded budgets."""
    client = _client()
    invalid_inputs: tuple[Any, ...] = (
        "message",
        b"message",
        object(),
        (),
        tuple({"role": "user", "content": "x"} for _ in range(65)),
        (1,),
        ({"role": "owner", "content": "x"},),
        ({"role": 1, "content": "x"},),
        ({"role": "user", "content": 1},),
        ({"role": "user", "content": "x" * 200_001},),
        ({"role": "user", "content": "\ud800"},),
        (
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": "y", "extra": "z"},
        ),
        tuple(
            {"role": "user", "content": "x" * 200_000}
            for _ in range(6)
        ),
    )
    for invalid in invalid_inputs:
        with pytest.raises(
            ContextualOrchestratorError,
            match="orchestrator_policy_rejected",
        ):
            client._validate_messages(invalid)

    assert client._validate_messages(
        ({"role": "tool", "content": ""},)
    ) == [{"role": "tool", "content": ""}]


def test_strict_json_and_upstream_code_terminal_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover strict decoding, safe upstream code extraction, and node bounds."""
    client = _client()
    for body in (
        b"\xff",
        b'{"value": NaN}',
        b"[]",
        b'{"value":"\\ud800"}',
    ):
        with pytest.raises(
            ContextualOrchestratorError,
            match="orchestrator_malformed_response",
        ):
            client._strict_json(body)

    assert client._safe_upstream_error_code(b"not-json") is None
    assert client._safe_upstream_error_code(b'{"error":"bad"}') is None
    assert (
        client._safe_upstream_error_code(
            b'{"error":{"code":7}}'
        )
        is None
    )
    too_long = json.dumps(
        {"error": {"code": "x" * 129}}
    ).encode()
    assert client._safe_upstream_error_code(too_long) is None
    assert (
        client._safe_upstream_error_code(
            b'{"error":{"code":"stable"}}'
        )
        == "stable"
    )

    monkeypatch.setattr(client_module, "_MAX_JSON_DEPTH", 1)
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_malformed_response",
    ):
        client._strict_json(b'{"nested":{"value":1}}')


@pytest.mark.parametrize(
    "document",
    (
        {"choices": None, "orchestration": {"mode": "route", "trace": []}},
        {"choices": [1], "orchestration": {"mode": "route", "trace": []}},
        {"choices": [{}], "orchestration": {"mode": "route", "trace": []}},
        {
            "choices": [{"message": {"content": 7}}],
            "orchestration": {"mode": "route", "trace": []},
        },
        {
            "choices": [{"message": {"content": "\ud800"}}],
            "orchestration": {"mode": "route", "trace": []},
        },
        {
            "choices": [{"message": {"content": "ok"}}],
            "orchestration": None,
        },
        {
            "choices": [{"message": {"content": "ok"}}],
            "orchestration": {"mode": "route", "trace": "bad"},
        },
        {
            "choices": [{"message": {"content": "ok"}}],
            "orchestration": {"mode": "route", "trace": [1]},
        },
        {
            "choices": [{"message": {"content": "ok"}}],
            "orchestration": {
                "mode": "route",
                "trace": [{"usage": "bad"}],
            },
        },
    ),
)
def test_completion_shape_rejections(document: dict[str, object]) -> None:
    """Reject malformed nested response members before admitting evidence."""
    client = _client()
    body = json.dumps(document, ensure_ascii=True).encode()
    with pytest.raises(
        ContextualOrchestratorError,
        match="orchestrator_malformed_response",
    ):
        client._parse_completion(body)


def test_completion_accepts_an_empty_trace() -> None:
    """Allow a strict completion that contains no orchestration steps."""
    client = _client()
    completion = client._parse_completion(
        json.dumps(_payload(trace=[])).encode()
    )
    assert completion.trace == ()


class _PortClient:
    """Minimal candidate transport used to exercise port lifecycle branches."""

    def __init__(self) -> None:
        self.closed = False

    async def complete(
        self,
        _messages: object,
        *,
        mode: str,
    ) -> ContextualOrchestratorCompletion:
        """Return one strict completion."""
        return ContextualOrchestratorCompletion(
            answer="ok",
            mode=cast(Any, mode),
            trace=(),
        )

    async def aclose(self) -> None:
        """Record closure."""
        self.closed = True


@pytest.mark.parametrize("capacity", (0, 33))
def test_port_rejects_invalid_worker_capacity(capacity: int) -> None:
    """Reject worker counts outside the bounded production range."""
    with pytest.raises(
        ValueError,
        match="judge_capacity must be between 1 and 32",
    ):
        EmailWritingOrchestratorPort(
            cast(Any, _PortClient()),
            judge_capacity=capacity,
        )


@pytest.mark.asyncio
async def test_port_rejects_sync_use_on_event_loop_and_is_idempotent() -> None:
    """Keep sync compatibility off the event loop and close only once."""
    transport = _PortClient()
    port = EmailWritingOrchestratorPort(cast(Any, transport))
    with pytest.raises(
        RuntimeError,
        match="sync_completion_on_event_loop",
    ):
        port.complete(_MESSAGES, mode="route")

    await port.aclose()
    await port.aclose()
    assert transport.closed is True

    with pytest.raises(RuntimeError, match="orchestrator_port_closed"):
        await port.complete_candidate(_MESSAGES, mode="route")
    with pytest.raises(RuntimeError, match="orchestrator_port_closed"):
        await asyncio.to_thread(
            port.complete,
            _MESSAGES,
            mode="route",
        )


class _ScalarResult:
    """Minimal scalar result for owner-scoped query tests."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        """Return the stored scalar."""
        return self.value


class _Session:
    """Record executed SQLAlchemy statements."""

    def __init__(self, value: Any) -> None:
        self.value = value
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> _ScalarResult:
        """Record one query and return the configured scalar."""
        self.queries.append(query)
        return _ScalarResult(self.value)


@pytest.mark.asyncio
async def test_legacy_and_orchestrator_owner_scope_helpers() -> None:
    """Cover both legacy and modular owner-scope helper branches."""
    with_organization = scope_module.tenant_config_owner_filters(
        "user_alpha",
        "organization_alpha",
    )
    assert with_organization[1].right.value == "organization_alpha"
    personal = scope_module.tenant_config_owner_filters(
        "user_alpha",
        None,
    )
    assert personal[1].operator.__name__ == "is_"

    session = _Session(None)
    assert (
        await scope_module.get_scoped_tenant_config(
            cast(Any, session),
            "user_alpha",
            None,
        )
        is None
    )
    assert len(session.queries) == 1
    created = scope_module.new_scoped_tenant_config(
        "user_alpha",
        "organization_alpha",
    )
    assert created.user_id == "user_alpha"
    assert created.organization_id == "organization_alpha"

    orchestrator_personal = (
        scope_module.email_writing_orchestrator_owner_filters(
            "user_alpha",
            None,
        )
    )
    assert orchestrator_personal[1].operator.__name__ == "is_"
    assert scope_module._clean_orchestrator_value(None) is None
    assert scope_module._clean_orchestrator_value("  value  ") == "value"
    assert scope_module._clean_orchestrator_value("   ") is None


def test_configuration_model_text_validation_is_bounded() -> None:
    """Cover null, type, length, control, and valid normalization branches."""
    assert (
        config_api.EmailWritingOrchestratorConfigUpdate(
            model_profile_id=None
        ).model_profile_id
        is None
    )
    with pytest.raises(ValidationError):
        config_api.EmailWritingOrchestratorConfigUpdate(
            model_profile_id=cast(Any, 7)
        )
    with pytest.raises(ValidationError):
        config_api.EmailWritingOrchestratorConfigUpdate(
            model_profile_id="x" * 256
        )
    with pytest.raises(ValidationError):
        config_api.EmailWritingOrchestratorConfigUpdate(
            model_profile_id="line\nbreak"
        )
    assert (
        config_api.EmailWritingOrchestratorConfigUpdate(
            model_profile_id="  profile  "
        ).model_profile_id
        == "profile"
    )


@pytest.mark.asyncio
async def test_configuration_url_none_and_commit_failures_are_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the explicit-null endpoint and both database error branches."""

    async def absent(
        _value: str | None,
    ) -> ValidatedLLMProviderBaseURL | None:
        return None

    monkeypatch.setattr(
        config_api,
        "validate_llm_provider_base_url_details_async",
        absent,
    )
    assert await config_api._validated_orchestrator_url(None) is None

    async def no_existing(
        _session: Any,
        _user_id: str,
        _organization_id: str | None,
    ) -> None:
        return None

    monkeypatch.setattr(
        config_api,
        "get_scoped_email_writing_orchestrator_config",
        no_existing,
    )

    class FailingDatabase:
        """Fail commits with one configured exception."""

        def __init__(self, error: Exception) -> None:
            self.error = error
            self.added: list[object] = []

        def add(self, value: object) -> None:
            """Record the pending configuration."""
            self.added.append(value)

        async def commit(self) -> None:
            """Raise the configured persistence failure."""
            raise self.error

    auth = AuthContext(
        user_id="user_alpha",
        role="member",
        organization_id="organization_alpha",
        group_ids=(),
        workspace_id="workspace_alpha",
    )
    update = config_api.EmailWritingOrchestratorConfigUpdate(
        orchestrator_enabled=False,
        inference_credential="opaque-value",
    )

    with pytest.raises(HTTPException) as encrypted:
        await config_api.update_email_writing_orchestrator_config(
            update,
            cast(
                Any,
                FailingDatabase(
                    RuntimeError(
                        "ENCRYPTION_KEY is required: private configuration"
                    )
                ),
            ),
            auth,
        )
    assert encrypted.value.status_code == 503
    assert encrypted.value.detail == (
        "Server encryption key is not configured. "
        "Contact your workspace administrator."
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await config_api.update_email_writing_orchestrator_config(
            update,
            cast(
                Any,
                FailingDatabase(
                    RuntimeError("database unavailable")
                ),
            ),
            auth,
        )


def test_migration_executes_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the real migration against SQLite without dropping other data."""
    backend_root = Path(__file__).resolve().parents[1]
    migration_path = (
        backend_root
        / "alembic"
        / "versions"
        / "20260813_0001_add_email_writing_orchestrator_config.py"
    )
    module_name = "task5_email_writing_orchestrator_migration"
    spec = importlib.util.spec_from_file_location(
        module_name,
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE unrelated_record "
            "(unrelated_record_id INTEGER PRIMARY KEY)"
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)

        module.upgrade()
        module.upgrade()
        inspector = inspect(connection)
        assert inspector.has_table("email_writing_orchestrator_config")
        assert inspector.has_table("unrelated_record")

        module.downgrade()
        module.downgrade()
        inspector = inspect(connection)
        assert not inspector.has_table(
            "email_writing_orchestrator_config"
        )
        assert inspector.has_table("unrelated_record")
    engine.dispose()
