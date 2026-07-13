"""Live-test account loader + DB seed (the KV path).

The ``NARUON_TEST_*{N}`` secrets are read from the environment **only here, at
seed time** -- this is the accepted bootstrap transport into the DB-backed,
Fernet-encrypted credential store. Once seeded, the app/connector reads the
accounts from the database at runtime; it never calls ``os.getenv`` for these
credentials.

The loader is N-account-native: it iterates ``N = 1, 2, ...`` while
``NARUON_TEST_EMAIL{N}`` is present, so adding account 2 needs zero code change
-- only the secrets.

Per-account environment fields (``{N}`` suffix):

    NARUON_TEST_EMAIL{N}        login / username (required; presence gates N)
    NARUON_TEST_PASSWORD{N}     password (shared across the account's protocols)
    NARUON_TEST_IMAP_ADDR{N}    IMAP  host[:port]      (port inferred -> 993)
    NARUON_TEST_POP3_ADDR{N}    POP3  host[:port]      (port inferred -> 995)
    NARUON_TEST_SMTP_ADDR{N}    SMTP  host[:port]      (port inferred -> 587)
    NARUON_TEST_CALDAV_ADDR{N}  CalDAV base URL or host (https, 443)
    NARUON_TEST_CARDDAV_ADDR{N} CardDAV base URL or host; blank -> auto-discover
    NARUON_TEST_WEBDAV_ADDR{N}  (optional) WebDAV base URL or host
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.net_defaults import infer_address_port  # noqa: E402

logger = logging.getLogger(__name__)

ENV_PREFIX = "NARUON_TEST_"


@dataclass(frozen=True)
class MailEndpoint:
    host: str
    port: int


@dataclass
class LiveAccountSpec:
    """A parsed (network-free) description of one live-test account."""

    index: int
    email: str
    password: str | None
    imap: MailEndpoint | None = None
    pop3: MailEndpoint | None = None
    smtp: MailEndpoint | None = None
    caldav_url: str | None = None
    # CardDAV: an explicit base URL, or None when discovery is required.
    carddav_url: str | None = None
    carddav_needs_discovery: bool = False
    webdav_url: str | None = None

    @property
    def user_id(self) -> str:
        return f"naruon-test-{self.index}"

    @property
    def workspace_id(self) -> str:
        return f"workspace-naruon-test-{self.index}"

    @property
    def configured_protocols(self) -> list[str]:
        protocols: list[str] = []
        if self.imap:
            protocols.append("imap")
        if self.pop3:
            protocols.append("pop3")
        if self.smtp:
            protocols.append("smtp")
        if self.caldav_url:
            protocols.append("caldav")
        if self.carddav_url or self.carddav_needs_discovery:
            protocols.append("carddav")
        if self.webdav_url:
            protocols.append("webdav")
        return protocols


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env(environ: Mapping[str, str], name: str, index: int) -> str | None:
    return _clean(environ.get(f"{ENV_PREFIX}{name}{index}"))


def _mail_endpoint(
    protocol: str, raw_addr: str | None
) -> MailEndpoint | None:
    if raw_addr is None:
        return None
    host, port = infer_address_port(protocol, raw_addr)
    return MailEndpoint(host=host, port=port)


def _dav_base_url(raw_addr: str | None) -> str | None:
    """Normalize a DAV address into an https base URL, or None."""
    if raw_addr is None:
        return None
    value = raw_addr.strip()
    if not value:
        return None
    if value.startswith("https://"):
        return value.rstrip("/") or value
    if value.startswith("http://"):
        # Downstream clients require https; upgrade a bare http hint.
        value = "https://" + value[len("http://") :]
        return value.rstrip("/") or value
    # Bare host[:port] -> https origin.
    return f"https://{value.rstrip('/')}"


def parse_account(environ: Mapping[str, str], index: int) -> LiveAccountSpec | None:
    """Parse a single account at ``index`` (no network / DNS). None if absent."""
    email = _env(environ, "EMAIL", index)
    if email is None:
        return None

    carddav_raw = _env(environ, "CARDDAV_ADDR", index)
    carddav_url = _dav_base_url(carddav_raw)

    return LiveAccountSpec(
        index=index,
        email=email,
        password=_env(environ, "PASSWORD", index),
        imap=_mail_endpoint("imap", _env(environ, "IMAP_ADDR", index)),
        pop3=_mail_endpoint("pop3", _env(environ, "POP3_ADDR", index)),
        smtp=_mail_endpoint("smtp", _env(environ, "SMTP_ADDR", index)),
        caldav_url=_dav_base_url(_env(environ, "CALDAV_ADDR", index)),
        carddav_url=carddav_url,
        # Blank/absent CardDAV address => auto-discover from the email domain.
        carddav_needs_discovery=carddav_url is None,
        webdav_url=_dav_base_url(_env(environ, "WEBDAV_ADDR", index)),
    )


def parse_test_accounts(
    environ: Mapping[str, str], *, max_accounts: int = 64
) -> list[LiveAccountSpec]:
    """Parse every ``NARUON_TEST_*{N}`` account present in ``environ``.

    Iterates ``N = 1, 2, ...`` and stops at the first missing ``EMAIL{N}``.
    Purely string parsing -- no DB, no network -- so it is unit-testable with a
    fake env dict.
    """
    accounts: list[LiveAccountSpec] = []
    for index in range(1, max_accounts + 1):
        spec = parse_account(environ, index)
        if spec is None:
            break
        accounts.append(spec)
    return accounts


# --------------------------------------------------------------------------
# DB seeding (imports DB + discovery lazily so parsing stays dependency-free).
# --------------------------------------------------------------------------


async def _resolve_carddav_url(spec: LiveAccountSpec) -> tuple[str | None, str]:
    """Return ``(base_url, discovery_source)`` for a CardDAV account."""
    if spec.carddav_url is not None:
        return spec.carddav_url, "provided"
    from services.carddav_discovery import discover_carddav

    result = await discover_carddav(spec.email)
    if result is None:
        return None, "undiscovered"
    return result.base_url, result.discovery_source


async def _seed_account(session, spec: LiveAccountSpec) -> dict[str, object]:
    from sqlalchemy import select

    from db.models import CaldavAccount, CarddavAccount, TenantConfig, WebdavAccount

    seeded: dict[str, object] = {
        "user_id": spec.user_id,
        "account_index": spec.index,
        "protocols": [],
    }
    protocols: list[str] = seeded["protocols"]  # type: ignore[assignment]

    # --- Mail: TenantConfig (one row per account scope) -------------------
    result = await session.execute(
        select(TenantConfig).where(
            TenantConfig.user_id == spec.user_id,
            TenantConfig.organization_id.is_(None),
        )
    )
    tenant_config = result.scalar_one_or_none()
    if tenant_config is None:
        tenant_config = TenantConfig(user_id=spec.user_id, organization_id=None)
        session.add(tenant_config)

    if spec.imap:
        tenant_config.imap_server = spec.imap.host
        tenant_config.imap_port = spec.imap.port
        tenant_config.imap_username = spec.email
        tenant_config.imap_password = spec.password
        protocols.append("imap")
    if spec.pop3:
        tenant_config.pop3_server = spec.pop3.host
        tenant_config.pop3_port = spec.pop3.port
        tenant_config.pop3_username = spec.email
        tenant_config.pop3_password = spec.password
        protocols.append("pop3")
    if spec.smtp:
        tenant_config.smtp_server = spec.smtp.host
        tenant_config.smtp_port = spec.smtp.port
        tenant_config.smtp_username = spec.email
        tenant_config.smtp_password = spec.password
        protocols.append("smtp")

    # --- CalDAV -----------------------------------------------------------
    if spec.caldav_url:
        await _upsert_dav(
            session,
            CaldavAccount,
            spec,
            server_url=spec.caldav_url,
        )
        protocols.append("caldav")

    # --- CardDAV (auto-discovery when the address is blank/uncertain) -----
    carddav_url, discovery_source = await _resolve_carddav_url(spec)
    if carddav_url:
        await _upsert_dav(
            session,
            CarddavAccount,
            spec,
            server_url=carddav_url,
            discovery_source=discovery_source,
        )
        seeded["carddav_discovery_source"] = discovery_source
        protocols.append("carddav")
    elif spec.carddav_needs_discovery:
        # Required-but-failed discovery is a seeding failure, not a skip: a
        # run that never reaches a CardDAV endpoint must not report coverage.
        seeded["carddav_discovery_failed"] = True
        logger.info(
            "CardDAV auto-discovery found no endpoint for account %s.",
            spec.index,
        )

    # --- WebDAV (optional) ------------------------------------------------
    if spec.webdav_url:
        result = await session.execute(
            select(WebdavAccount).where(
                WebdavAccount.user_id == spec.user_id,
                WebdavAccount.organization_id.is_(None),
                WebdavAccount.workspace_id == spec.workspace_id,
            )
        )
        webdav = result.scalar_one_or_none()
        if webdav is None:
            webdav = WebdavAccount(
                user_id=spec.user_id,
                organization_id=None,
                workspace_id=spec.workspace_id,
            )
            session.add(webdav)
        webdav.server_url = spec.webdav_url
        webdav.username = spec.email
        webdav.credentials_encrypted = spec.password or ""
        protocols.append("webdav")

    return seeded


async def _upsert_dav(
    session,
    model,
    spec: LiveAccountSpec,
    *,
    server_url: str,
    discovery_source: str | None = None,
) -> None:
    from sqlalchemy import select

    result = await session.execute(
        select(model).where(
            model.user_id == spec.user_id,
            model.server_url == server_url,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = model(user_id=spec.user_id, server_url=server_url)
        session.add(account)
    account.username = spec.email
    account.credentials_encrypted = spec.password or ""
    if hasattr(account, "discovery_source"):
        account.discovery_source = discovery_source
    if hasattr(account, "account_index"):
        account.account_index = spec.index
    if hasattr(account, "workspace_id"):
        account.workspace_id = spec.workspace_id


async def seed_test_accounts(
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Seed every configured live-test account into the DB. Returns a summary."""
    import os

    from db.session import AsyncSessionLocal

    if environ is None:
        environ = os.environ

    specs = parse_test_accounts(environ)
    if not specs:
        logger.warning(
            "No NARUON_TEST_EMAIL{N} secrets found; nothing to seed."
        )
        return []

    summaries: list[dict[str, object]] = []
    async with AsyncSessionLocal() as session:
        for spec in specs:
            summaries.append(await _seed_account(session, spec))
        await session.commit()

    for summary in summaries:
        logger.info(
            "Seeded live-test account %s (protocols: %s)",
            summary["user_id"],
            ",".join(summary["protocols"]),  # type: ignore[arg-type]
        )
    return summaries


def main() -> int:
    logging.basicConfig(level="INFO")
    summaries = asyncio.run(seed_test_accounts())
    print(f"Seeded {len(summaries)} live-test account(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
