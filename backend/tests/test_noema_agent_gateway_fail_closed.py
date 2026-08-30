"""Fail-closed regressions for Noema's contextual-orchestrator client path."""

from __future__ import annotations

from typing import Any

import pytest

from services import noema_agent
from services.noema_agent import build_noema_agent, run_noema_agent
from services.orchestrator_gateway import OrchestratorGateway


def _gateway() -> OrchestratorGateway:
    """Return one dedicated contextual-orchestrator gateway fixture."""
    return OrchestratorGateway(
        inference_token="naruon-orch-inference-token",
        base_url="https://orchestrator.example/v1",
    )


@pytest.mark.asyncio
async def test_run_agent_maps_http_client_validation_failure_to_gateway_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS/allowlist validation failures never escape the public entrypoint."""

    async def _gateway_from_kv(*_args: Any, **_kwargs: Any) -> OrchestratorGateway:
        return _gateway()

    async def _validation_failure(_base_url: str) -> tuple[str, object]:
        raise ValueError("host_not_allowlisted: orchestrator.example")

    monkeypatch.setattr(noema_agent, "resolve_orchestrator_gateway", _gateway_from_kv)
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: {"runtime": object()})
    monkeypatch.setattr(
        noema_agent,
        "build_llm_provider_http_client",
        _validation_failure,
    )

    result = await run_noema_agent(
        object(),  # type: ignore[arg-type]
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )

    assert result.status == "unavailable"
    assert result.error_code == "orchestrator_gateway_unavailable"
    assert result.provider_name == "contextual-orchestrator"
    assert result.model_alias == "contextual-orchestrator"
    assert "host_not_allowlisted" not in (result.notice or "")


@pytest.mark.asyncio
async def test_build_agent_rejects_missing_base_url_before_openai_client_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected URL closes its pinned client and cannot fall back to OpenAI."""

    state = {"closed": False, "openai_created": False}

    class _PinnedClient:
        async def aclose(self) -> None:
            state["closed"] = True

    async def _missing_base_url(_base_url: str) -> tuple[None, _PinnedClient]:
        return None, _PinnedClient()

    def _unexpected_openai(*_args: Any, **_kwargs: Any) -> object:
        state["openai_created"] = True
        return object()

    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: {"runtime": object()})
    monkeypatch.setattr(
        noema_agent,
        "build_llm_provider_http_client",
        _missing_base_url,
    )
    monkeypatch.setattr(noema_agent, "AsyncOpenAI", _unexpected_openai)

    with pytest.raises(ValueError, match="orchestrator_gateway_unavailable"):
        await build_noema_agent(_gateway())

    assert state == {"closed": True, "openai_created": False}
