"""contextual-orchestrator inference gateway for in-process agents.

naruon is a consumer of ContextualWisdomLab/contextual-orchestrator. This
module resolves the dedicated gateway inference token and the HTTPS ``/v1``
base URL from the Fernet-encrypted tenant credential store (the KV). It does
not read ``os.getenv`` at request time, does not hold upstream provider keys,
and does not pick or fail over across models. The orchestrator auto-discovers
upstream models and itself selects min-cost / max-performance (Fugu /
Conductor / TRINITY); naruon always sends the single model alias
``contextual-orchestrator``.

Upstream org secrets (``NVIDIA_NIM_API_KEY``, ``NVIDIA_NIM_API_KEY_SUB``,
``BYTEZ_API_KEY``, ``OPENROUTER_API_KEY``, ``OPENAI_API_KEY``) belong in the
orchestrator KV, not in naruon request-time config. GitHub Models /
``COPILOT_GITHUB_TOKEN`` are never a Noema path.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession

from services.llm_provider_urls import validate_llm_provider_base_url
from services.tenant_config_scope import get_scoped_tenant_config

ORCHESTRATOR_MODEL_ALIAS = "contextual-orchestrator"

# Named so tests can prove naruon never consumes these at request time.
# They are registered in the orchestrator KV, not in naruon.
UPSTREAM_PROVIDER_SECRET_NAMES = frozenset(
    {
        "NVIDIA_NIM_API_KEY",
        "NVIDIA_NIM_API_KEY_SUB",
        "BYTEZ_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "COPILOT_GITHUB_TOKEN",
    }
)

FORBIDDEN_GATEWAY_HOSTS = frozenset(
    {
        "models.github.ai",
        "api.githubcopilot.com",
        "copilot-proxy.githubusercontent.com",
    }
)


@dataclass(frozen=True)
class OrchestratorGateway:
    """Single-alias OpenAI-compatible gateway naruon may call."""

    inference_token: str
    base_url: str
    model_alias: str = ORCHESTRATOR_MODEL_ALIAS
    model_candidates: tuple[str, ...] = ()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def validate_orchestrator_gateway_url(value: str) -> str:
    """Require HTTPS and a path that ends in ``/v1``; reject GitHub Models."""
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError("orchestrator gateway URL is required")

    parsed = urlsplit(candidate)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https":
        raise ValueError("orchestrator gateway URL must be HTTPS")
    if (
        not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("orchestrator gateway URL is not allowed")
    if hostname in FORBIDDEN_GATEWAY_HOSTS:
        raise ValueError("orchestrator gateway URL is not allowed")

    path = (parsed.path or "").rstrip("/")
    if path != "/v1" and not path.endswith("/v1"):
        raise ValueError("orchestrator gateway URL must end in /v1")

    return urlunsplit(("https", parsed.netloc.lower(), path, "", ""))


async def resolve_orchestrator_gateway(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> OrchestratorGateway | None:
    """Resolve the dedicated Noema gateway from the Fernet tenant KV.

    Returns ``None`` (fail closed) when the token or HTTPS ``/v1`` URL is
    missing or rejected. Never reads the process environment.
    """
    tenant_config = await get_scoped_tenant_config(session, user_id, organization_id)
    if tenant_config is None:
        return None

    base_url = _clean(getattr(tenant_config, "noema_orchestrator_base_url", None))
    token = _clean(getattr(tenant_config, "noema_orchestrator_token", None))
    if not base_url or not token:
        return None

    try:
        shaped = validate_orchestrator_gateway_url(base_url)
    except ValueError:
        return None

    try:
        allowlisted = validate_llm_provider_base_url(shaped)
    except ValueError:
        return None
    if not allowlisted:
        return None

    try:
        validated = validate_orchestrator_gateway_url(allowlisted)
    except ValueError:
        return None

    return OrchestratorGateway(
        inference_token=token,
        base_url=validated,
        model_alias=ORCHESTRATOR_MODEL_ALIAS,
        model_candidates=(),
    )
