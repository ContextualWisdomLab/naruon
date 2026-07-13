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


def _connector_scope(
    environ: Mapping[str, str],
) -> tuple[str | None, frozenset[str] | None]:
    """Return the (organization_id, user-id allowlist) this runner may serve.

    ``NARUON_CONNECTOR_ORGANIZATION_ID`` selects the organization scope; when
    unset the runner serves only personal-scope rows (``organization_id IS
    NULL``). ``NARUON_CONNECTOR_USER_IDS`` (comma-separated) further restricts
    loading to an explicit user allowlist; when set but empty it loads nothing.
    """
    organization_id = (
        environ.get("NARUON_CONNECTOR_ORGANIZATION_ID") or ""
    ).strip() or None
    raw_user_ids = (environ.get("NARUON_CONNECTOR_USER_IDS") or "").strip()
    user_ids: frozenset[str] | None = None
    if raw_user_ids:
        user_ids = frozenset(
            user_id.strip() for user_id in raw_user_ids.split(",") if user_id.strip()
        )
    return organization_id, user_ids


async def _load_seeded_handlers(
    environ: Mapping[str, str] = os.environ,
) -> dict[str, object]:
    """Construct local protocol handlers from the seeded DB accounts.

    The connector reads mail/DAV credentials from the database at runtime (the
    KV path) -- never from ``os.getenv``. Loading is bound to the runner's
    configured scope (see ``_connector_scope``): a shared multi-tenant database
    never hands this runner another tenant's credentials. Legacy
    ``caldav_accounts`` rows carry no organization column, so they load only
    for personal-scope runners. Every DAV source is keyed by its opaque
    ``source_uid``, so gateway payloads select accounts by unguessable scoped
    identifiers rather than raw user ids.
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

    organization_id, user_ids = _connector_scope(environ)

    def _scoped(statement, model, *, has_organization_column: bool = True):
        if has_organization_column:
            if organization_id is None:
                statement = statement.where(model.organization_id.is_(None))
            else:
                statement = statement.where(
                    model.organization_id == organization_id
                )
        if user_ids is not None:
            statement = statement.where(model.user_id.in_(sorted(user_ids)))
        return statement

    mail_accounts: list[LocalMailAccountConfig] = []
    dav_sources: list[LocalDavSourceConfig] = []

    async with AsyncSessionLocal() as session:
        tenant_rows = (
            (await session.execute(_scoped(select(TenantConfig), TenantConfig)))
            .scalars()
            .all()
        )
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

        if organization_id is None:
            caldav_rows = (
                (
                    await session.execute(
                        _scoped(
                            select(CaldavAccount),
                            CaldavAccount,
                            has_organization_column=False,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for caldav in caldav_rows:
                dav_sources.append(
                    LocalDavSourceConfig(
                        source_id=f"caldav_{caldav.user_id}",
                        protocol="caldav",
                        base_url=caldav.server_url,
                        username=caldav.username,
                        password=caldav.credentials_encrypted,
                    )
                )
        carddav_rows = (
            (await session.execute(_scoped(select(CarddavAccount), CarddavAccount)))
            .scalars()
            .all()
        )
        for carddav in carddav_rows:
            dav_sources.append(
                LocalDavSourceConfig(
                    source_id=carddav.source_uid,
                    protocol="carddav",
                    base_url=carddav.server_url,
                    username=carddav.username,
                    password=carddav.credentials_encrypted,
                    writeback_enabled=bool(carddav.writeback_enabled),
                )
            )
        webdav_rows = (
            (await session.execute(_scoped(select(WebdavAccount), WebdavAccount)))
            .scalars()
            .all()
        )
        for webdav in webdav_rows:
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
    # Validate required connector configuration before any database work, so a
    # misconfigured connector fails closed on config (exit 2) rather than
    # attempting a DB load it has no tokens to use.
    _required_env(environ, "NARUON_REGISTRATION_TOKEN")
    _required_env(environ, "NARUON_SESSION_TOKEN")

    handlers: dict[str, object] | None = None
    if (environ.get("DATABASE_URL") or "").strip():
        try:
            handlers = await _load_seeded_handlers(environ)
        except Exception as exc:  # noqa: BLE001 - a configured DB must load, or we stop
            logger.error(
                "Failed to load seeded DB handlers (%s); refusing to start a "
                "connector that would report healthy without its adapters.",
                type(exc).__name__,
            )
            return 3
    else:
        logger.info(
            "DATABASE_URL is not configured; starting without local adapters."
        )
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
