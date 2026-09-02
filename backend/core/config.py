from typing import Any, cast
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env_paths import ENV_FILE_PATHS, operator_env_file_paths
from core.runtime_secrets import (
    DEFAULT_ENCRYPTION_KEY_ID,
    validate_auth_session_hmac_secret_value,
)
from core.url_validation import (
    parse_allowed_hosts,
    validate_https_url_host_details,
    validate_same_or_subdomain_host,
)

DEFAULT_ORIGIN_PORTS = {
    "http": 80,
    "https": 443,
}


def canonical_origin(scheme: str, hostname: str, port: int | None) -> str:
    normalized_scheme = scheme.lower()
    normalized_host = hostname.lower()
    if ":" in normalized_host and not normalized_host.startswith("["):
        normalized_host = f"[{normalized_host}]"
    default_port = DEFAULT_ORIGIN_PORTS.get(normalized_scheme)
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{normalized_scheme}://{normalized_host}{port_suffix}"


def parse_allowed_cors_origins(raw_origins: str) -> list[str]:
    origins: list[str] = []
    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip()
        if not origin:
            continue
        if "*" in origin:
            raise ValueError("ALLOWED_CORS_ORIGINS must not include wildcards")

        parsed = urlsplit(origin)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("ALLOWED_CORS_ORIGINS entries must use http or https")
        if parsed.username or parsed.password:
            raise ValueError("ALLOWED_CORS_ORIGINS entries must not include userinfo")
        if not parsed.netloc or not parsed.hostname:
            raise ValueError("ALLOWED_CORS_ORIGINS entries must include a host")
        if parsed.path or parsed.query or parsed.fragment:
            raise ValueError(
                "ALLOWED_CORS_ORIGINS entries must be origins without path, query, or fragment"
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError(
                "ALLOWED_CORS_ORIGINS entries must include a valid port"
            ) from exc

        origins.append(canonical_origin(parsed.scheme, parsed.hostname, port))
    return origins


class Settings(BaseSettings):
    DATABASE_URL: str
    READONLY_DATABASE_URL: str | None = None
    # Connection-pool tuning. Sizing values default to None (SQLAlchemy
    # defaults) so behavior is unchanged until an operator sets them.
    # pre_ping detects dead connections at checkout; recycle avoids
    # server-side idle timeouts killing pooled connections.
    DB_POOL_SIZE: int | None = None
    DB_MAX_OVERFLOW: int | None = None
    DB_POOL_TIMEOUT_SECONDS: int | None = None
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_PRE_PING: bool = True
    DEBUG: bool = False
    RUNTIME_ENVIRONMENT: str = "production"
    AUTH_SESSION_HMAC_SECRET: SecretStr | None = None
    ENCRYPTION_KEY: SecretStr | None = None
    ENCRYPTION_KEY_ID: str = DEFAULT_ENCRYPTION_KEY_ID
    ENCRYPTION_PREVIOUS_KEYS: SecretStr | None = None
    CONTROL_PLANE_DOMAIN: str = "naruon.net"
    ALLOWED_SMTP_HOSTS: str = ""
    ALLOWED_SMTP_PORTS: str = "465,587"
    ALLOWED_IMAP_HOSTS: str = ""
    ALLOWED_IMAP_PORTS: str = "993"
    ALLOWED_POP3_HOSTS: str = ""
    ALLOWED_POP3_PORTS: str = "995"
    ALLOWED_LLM_BASE_URL_HOSTS: str = ""
    ALLOW_LOCAL_LLM_PROVIDERS: bool = False
    # NewsDOM PDF DOM recognition sidecar. Mirrors the LLM provider allowlist
    # controls: the base URL host must be listed here before any request is
    # pinned and dispatched, and container-name / loopback hosts are only
    # accepted when ALLOW_LOCAL_NEWSDOM_PROVIDERS is enabled (dev / docker).
    ALLOWED_NEWSDOM_HOSTS: str = ""
    ALLOW_LOCAL_NEWSDOM_PROVIDERS: bool = False
    # Host allowlist for the scopeweave promotion target. The per-workspace
    # base URL and PAT themselves live encrypted in the database
    # (scopeweave_promotion_target); this setting only pins which hosts an
    # operator is permitted to promote work items to (SSRF host allowlist).
    ALLOWED_SCOPEWEAVE_HOSTS: str = ""
    ALLOWED_CORS_ORIGINS: str = ""
    ENABLE_PROMETHEUS_METRICS: bool = False
    # Best-effort projection of imported-email content segments into the project
    # semantic graph. Off by default; failure never affects email import.
    PROJECT_GRAPH_EXTRACTION_ENABLED: bool = False
    # Which extractor projects segments into the graph, resolved through the
    # named+versioned KG extractor seam (services/project_graph/extractor_registry):
    #   "keyword"      — deterministic baseline, an intentional always-on
    #                    non-LLM product mode in its own right,
    #   "llm"          — grounded LLM extraction; policy-disabled (raises
    #                    unconditionally) as of extractor_registry.py
    #                    ADR-0005 Revision 8 -- Naruon holds no production
    #                    LLM provider/model authority outside a released
    #                    contextual-orchestrator consumer contract,
    #   "orchestrator" — the same grounded LLM extraction routed through the
    #                    contextual-orchestrator gateway (see below); not yet
    #                    operational pending that release.
    # Only "keyword" (or an explicit request for it) resolves to the
    # deterministic extractor. "llm"/"orchestrator" never fall back to it: an
    # unavailable or failed request propagates instead of silently
    # persisting a keyword-derived result under the request's name. An
    # unrecognized value also raises rather than defaulting to "keyword".
    PROJECT_GRAPH_EXTRACTOR: str = "keyword"
    # OpenAI-compatible base URL of the contextual-orchestrator LLM gateway that
    # grounded extraction is routed through when PROJECT_GRAPH_EXTRACTOR is
    # "orchestrator". Must be HTTPS and exact-host allowlisted by
    # ALLOWED_LLM_BASE_URL_HOSTS (enforced by build_llm_provider_http_client);
    # unset (or any other precondition orchestrator routing needs) raises
    # ExtractorUnavailableError rather than falling back to the deterministic
    # keyword extractor (extractor_registry.py ADR-0005 Revision 8). The
    # provider API key remains the tenant's Fernet-encrypted credential.
    PROJECT_GRAPH_ORCHESTRATOR_BASE_URL: str | None = None
    DATA_REGION: str = "kr"
    SECONDARY_DATA_REGION: str = "eu"
    SECURITY_CONTENT_SECURITY_POLICY: str = (
        "default-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    # OpenAI Settings
    OPENAI_BASE_URL: str | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_MODEL: str = "gpt-4o"

    # Codec Carver audio-conversion integration (operator-configured in-cluster
    # Service base URL, e.g. http://codec-carver:8000). Converts recording
    # attachments to FLAC/Opus for STT / omni-modal input. Disabled while unset.
    CODEC_CARVER_BASE_URL: str | None = None
    CODEC_CARVER_API_KEY: SecretStr | None = None

    # Clearfolio document-viewer integration (operator-configured in-cluster
    # Service base URL, e.g. http://clearfolio:8080). Integration is disabled
    # while unset — the 미리보기 surface stays hidden.
    CLEARFOLIO_BASE_URL: str | None = None

    # Hybrid search fusion (see services/hybrid_retrieval/score_fusion.py;
    # defaults grounded in Bruch, Gai & Ingber 2023 and Cormack et al. 2009)
    SEARCH_FUSION_STRATEGY: str = "convex_combination"
    SEARCH_FUSION_SEMANTIC_WEIGHT: float = 0.7
    SEARCH_RRF_RANK_CONSTANT: int = 60
    SEARCH_CHANNEL_CANDIDATE_LIMIT: int = 50
    SEARCH_MINIMUM_FUSED_SCORE: float = 0.05

    # OIDC Settings
    OIDC_ISSUER_URL: str | None = None
    OIDC_CLIENT_ID: str | None = None
    OIDC_JWKS_URL: str | None = None
    ALLOWED_OIDC_HOSTS: str = ""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATHS,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        values.setdefault("_env_file", operator_env_file_paths())
        super().__init__(**values)

    @field_validator("READONLY_DATABASE_URL", mode="before")
    @classmethod
    def normalize_blank_readonly_database_url(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_session_secret(self) -> "Settings":
        parse_allowed_cors_origins(self.ALLOWED_CORS_ORIGINS)

        configured = self.AUTH_SESSION_HMAC_SECRET
        if configured is None:
            raise ValueError(
                "AUTH_SESSION_HMAC_SECRET is required in all runtime environments"
            )

        validate_auth_session_hmac_secret_value(configured.get_secret_value())
        oidc_values = {
            "OIDC_ISSUER_URL": self.OIDC_ISSUER_URL,
            "OIDC_CLIENT_ID": self.OIDC_CLIENT_ID,
            "OIDC_JWKS_URL": self.OIDC_JWKS_URL,
        }
        configured_oidc_values = {
            setting_name: setting_value
            for setting_name, setting_value in oidc_values.items()
            if setting_value
        }
        if configured_oidc_values and len(configured_oidc_values) != len(oidc_values):
            raise ValueError(
                "OIDC_ISSUER_URL, OIDC_CLIENT_ID, and OIDC_JWKS_URL must be set together"
            )
        if len(configured_oidc_values) == len(oidc_values):
            allowed_oidc_hosts = parse_allowed_hosts(self.ALLOWED_OIDC_HOSTS)
            if not allowed_oidc_hosts:
                raise ValueError(
                    "ALLOWED_OIDC_HOSTS must list trusted OIDC issuer and JWKS hosts"
                )
            issuer_url = validate_https_url_host_details(
                "OIDC_ISSUER_URL",
                self.OIDC_ISSUER_URL or "",
                allowed_oidc_hosts,
                "ALLOWED_OIDC_HOSTS",
            )
            jwks_url = validate_https_url_host_details(
                "OIDC_JWKS_URL",
                self.OIDC_JWKS_URL or "",
                allowed_oidc_hosts,
                "ALLOWED_OIDC_HOSTS",
            )
            validate_same_or_subdomain_host(
                "OIDC_JWKS_URL",
                jwks_url.hostname,
                "OIDC_ISSUER_URL",
                issuer_url.hostname,
            )
        return self

    @property
    def ALLOWED_CORS_ORIGINS_LIST(self) -> list[str]:
        return parse_allowed_cors_origins(self.ALLOWED_CORS_ORIGINS)


settings = Settings(**cast(dict[str, Any], {}))  # type: ignore
