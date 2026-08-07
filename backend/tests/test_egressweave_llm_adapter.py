"""Contract tests for the naruon-owned EgressWeave LLM adapter."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.config import settings
from services import egressweave_llm_adapter, llm_service


class _SentinelClient:
    """Minimal client sentinel returned by the injected EgressWeave builder."""


@pytest.mark.asyncio
async def test_default_openai_uses_exact_builtin_authority_without_changing_none_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default provider stays ``None`` to callers but is pinned internally."""
    captured: dict[str, object] = {}
    sentinel = _SentinelClient()

    async def fake_build(base_url: str, *, policy):
        captured["base_url"] = base_url
        captured["policy"] = policy
        return "https://api.openai.com/v1", sentinel

    monkeypatch.setattr(
        egressweave_llm_adapter,
        "_build_egress_http_client",
        fake_build,
    )

    normalized, client = await egressweave_llm_adapter.build_llm_provider_http_client(
        None
    )

    assert normalized is None
    assert client is sentinel
    assert captured["base_url"] == "https://api.openai.com/v1"
    policy = captured["policy"]
    assert policy.allowed_authorities == frozenset({("api.openai.com", 443)})
    assert policy.allow_local is False


@pytest.mark.asyncio
async def test_custom_provider_maps_operator_allowlist_to_one_exact_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A custom provider receives only its reviewed host-and-port pair."""
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "api.example.com")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", False)
    captured: dict[str, object] = {}
    sentinel = _SentinelClient()

    async def fake_build(base_url: str, *, policy):
        captured["base_url"] = base_url
        captured["policy"] = policy
        return "https://api.example.com:8443/v1", sentinel

    monkeypatch.setattr(
        egressweave_llm_adapter,
        "_build_egress_http_client",
        fake_build,
    )

    normalized, client = await egressweave_llm_adapter.build_llm_provider_http_client(
        "https://api.example.com:8443/v1"
    )

    assert normalized == "https://api.example.com:8443/v1"
    assert client is sentinel
    policy = captured["policy"]
    assert policy.allowed_authorities == frozenset({("api.example.com", 8443)})
    assert policy.allow_local is False


@pytest.mark.asyncio
async def test_local_container_requires_both_exact_allowlist_and_local_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local widening never grants an unlisted hostname or port implicitly."""
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    captured: dict[str, object] = {}
    sentinel = _SentinelClient()

    async def fake_build(base_url: str, *, policy):
        captured["policy"] = policy
        return base_url, sentinel

    monkeypatch.setattr(
        egressweave_llm_adapter,
        "_build_egress_http_client",
        fake_build,
    )

    normalized, client = await egressweave_llm_adapter.build_llm_provider_http_client(
        "http://ollama:11434/v1"
    )

    assert normalized == "http://ollama:11434/v1"
    assert client is sentinel
    policy = captured["policy"]
    assert policy.allowed_authorities == frozenset({("ollama", 11434)})
    assert policy.allow_local is True


@pytest.mark.asyncio
async def test_local_opt_in_does_not_authorize_unlisted_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``allow_local`` widens address class only after exact host authorization."""
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    called = False

    async def fake_build(base_url: str, *, policy):
        nonlocal called
        called = True
        raise AssertionError("unlisted authority reached EgressWeave builder")

    monkeypatch.setattr(
        egressweave_llm_adapter,
        "_build_egress_http_client",
        fake_build,
    )

    with pytest.raises(ValueError, match="LLM provider base URL is not allowed"):
        await egressweave_llm_adapter.build_llm_provider_http_client(
            "http://localhost:11434/v1"
        )

    assert called is False


def test_llm_service_routes_through_application_owned_egressweave_adapter() -> None:
    """Primary summary/translation/reply calls must consume the new adapter seam."""
    assert (
        llm_service.build_llm_provider_http_client
        is egressweave_llm_adapter.build_llm_provider_http_client
    )


def test_adapter_uses_only_egressweave_public_network_boundary() -> None:
    """The new adapter must not recreate HTTPX/HTTPCore private transport code."""
    source = Path(egressweave_llm_adapter.__file__).read_text(encoding="utf-8")
    assert "httpcore" not in source
    assert "httpx._" not in source
    assert "from egressweave import" in source


def test_runtime_dependency_uses_hashed_released_egressweave_distribution() -> None:
    """Runtime integration must use one released version with local SHA-256 hashes."""
    requirements = Path("requirements.txt")
    lockfile = Path("requirements-hashes.txt")
    if not requirements.exists():
        requirements = Path("backend/requirements.txt")
        lockfile = Path("backend/requirements-hashes.txt")

    requirement_text = requirements.read_text(encoding="utf-8")
    version_match = re.search(
        r"(?m)^egressweave==(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$",
        requirement_text,
    )
    assert version_match is not None, (
        "EgressWeave must be consumed from a released immutable distribution; "
        "direct VCS/source-archive pins are not an accepted runtime boundary"
    )

    locked_version = version_match.group("version")
    lock_lines = lockfile.read_text(encoding="utf-8").splitlines()
    package_prefix = f"egressweave=={locked_version} "
    package_index = next(
        (index for index, line in enumerate(lock_lines) if line.startswith(package_prefix)),
        None,
    )
    assert package_index is not None, "released EgressWeave must be present in the hash lock"

    hash_lines: list[str] = []
    for line in lock_lines[package_index + 1 :]:
        if line.startswith("    --hash=sha256:"):
            hash_lines.append(line)
            continue
        if line.startswith("    ") or line.startswith("#") or not line:
            continue
        break

    assert hash_lines, "EgressWeave runtime distribution must have local SHA-256 hashes"
    assert all(
        re.fullmatch(r"    --hash=sha256:[0-9a-f]{64}(?: \\)?", line)
        for line in hash_lines
    )
