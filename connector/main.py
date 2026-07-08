import asyncio
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote

_REPO_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if _REPO_BACKEND.is_dir():
    sys.path.insert(0, str(_REPO_BACKEND))

from runner.connector import SelfHostedConnector  # noqa: E402

DEFAULT_WS_URL = "wss://naruon.net/ws/runner/{registration_token}"

logger = logging.getLogger("naruon.connector")


class ConnectorConfigError(ValueError):
    """Raised when required connector runtime configuration is missing."""


def _required_env(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ConnectorConfigError(f"{name} is required")
    return value


def _target_ws_url(environ: Mapping[str, str], registration_token: str) -> str:
    template = (environ.get("NARUON_CONTROL_PLANE_WS_URL") or DEFAULT_WS_URL).strip()
    escaped_token = quote(registration_token, safe="")
    if "{registration_token}" in template:
        return template.format(registration_token=escaped_token)
    return f"{template.rstrip('/')}/{escaped_token}"


def build_connector(
    environ: Mapping[str, str] = os.environ,
    *,
    handlers: Mapping[str, object] | None = None,
) -> SelfHostedConnector:
    registration_token = _required_env(environ, "NARUON_REGISTRATION_TOKEN")
    session_token = _required_env(environ, "NARUON_SESSION_TOKEN")
    handler_kwargs = dict(handlers) if handlers else {}
    return SelfHostedConnector(
        _target_ws_url(environ, registration_token),
        session_token,
        **handler_kwargs,
    )


async def _load_seeded_handlers() -> dict[str, object]:
    """Construct local protocol handlers from the seeded DB accounts.

    The connector reads mail/DAV credentials from the database at runtime (the
    KV path) -- never from ``os.getenv``. This builds ``LocalMailAdapters`` and
    ``LocalDavAdapters`` from the seeded ``tenant_configs`` /
    ``caldav_accounts`` / ``carddav_accounts`` / ``webdav_accounts`` rows and
    returns the handler callables to wire into the connector.
    """
    from sqlalchemy import select

    from db.models import (
        CaldavAccount,
        CarddavAccount,
        TenantConfig,
        WebdavAccount,
    )
    from db.session import AsyncSessionLocal
    from runner.local_dav_adapters import LocalDavAdapters, LocalDavSourceConfig
    from runner.local_mail_adapters import LocalMailAccountConfig, LocalMailAdapters

    mail_accounts: list[LocalMailAccountConfig] = []
    dav_sources: list[LocalDavSourceConfig] = []

    async with AsyncSessionLocal() as session:
        tenant_rows = (await session.execute(select(TenantConfig))).scalars().all()
        for row in tenant_rows:
            mail_accounts.append(
                LocalMailAccountConfig(
                    account=row.user_id,
                    user_id=row.user_id,
                    organization_id=row.organization_id,
                    smtp_server=row.smtp_server,
                    smtp_port=row.smtp_port,
                    smtp_username=row.smtp_username,
                    smtp_password=row.smtp_password,
                    imap_server=row.imap_server,
                    imap_port=row.imap_port,
                    imap_username=row.imap_username,
                    imap_password=row.imap_password,
                )
            )

        for caldav in (await session.execute(select(CaldavAccount))).scalars().all():
            dav_sources.append(
                LocalDavSourceConfig(
                    source_id=f"caldav_{caldav.user_id}",
                    protocol="caldav",
                    base_url=caldav.server_url,
                    username=caldav.username,
                    password=caldav.credentials_encrypted,
                )
            )
        for carddav in (await session.execute(select(CarddavAccount))).scalars().all():
            dav_sources.append(
                LocalDavSourceConfig(
                    source_id=f"carddav_{carddav.user_id}",
                    protocol="carddav",
                    base_url=carddav.server_url,
                    username=carddav.username,
                    password=carddav.credentials_encrypted,
                )
            )
        for webdav in (await session.execute(select(WebdavAccount))).scalars().all():
            dav_sources.append(
                LocalDavSourceConfig(
                    source_id=webdav.source_uid,
                    protocol="webdav",
                    base_url=webdav.server_url,
                    username=webdav.username,
                    password=webdav.credentials_encrypted,
                    writeback_enabled=bool(webdav.writeback_enabled),
                )
            )

    mail_adapters = LocalMailAdapters(mail_accounts)
    dav_adapters = LocalDavAdapters(dav_sources)
    return {
        "imap_fetch_handler": mail_adapters.fetch_imap,
        "smtp_send_handler": mail_adapters.send_smtp,
        "webdav_write_handler": dav_adapters.write_webdav,
        "caldav_write_handler": dav_adapters.write_caldav,
        "carddav_write_handler": dav_adapters.write_carddav,
    }


async def amain(environ: Mapping[str, str] = os.environ) -> int:
    try:
        handlers = await _load_seeded_handlers()
    except Exception as exc:  # noqa: BLE001 - fail open to a handler-less connector
        logger.warning(
            "Could not load seeded DB handlers (%s); starting without local adapters.",
            type(exc).__name__,
        )
        handlers = None
    connector = build_connector(environ, handlers=handlers)
    await connector.connect()
    return 0


def main() -> int:
    logging.basicConfig(level=os.environ.get("NARUON_CONNECTOR_LOG_LEVEL", "INFO"))
    try:
        return asyncio.run(amain())
    except ConnectorConfigError as exc:
        logger.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
