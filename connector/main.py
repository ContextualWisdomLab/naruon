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
    pass


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


def build_connector(environ: Mapping[str, str] = os.environ) -> SelfHostedConnector:
    registration_token = _required_env(environ, "NARUON_REGISTRATION_TOKEN")
    session_token = _required_env(environ, "NARUON_SESSION_TOKEN")
    return SelfHostedConnector(
        _target_ws_url(environ, registration_token),
        session_token,
    )


async def amain(environ: Mapping[str, str] = os.environ) -> int:
    connector = build_connector(environ)
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
