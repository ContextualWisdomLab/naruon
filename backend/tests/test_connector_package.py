import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from connector import main as connector_main  # noqa: E402
from runner.connector import SelfHostedConnector, _log_safe_ws_url  # noqa: E402


def test_connector_requires_registration_token():
    with pytest.raises(connector_main.ConnectorConfigError):
        connector_main.build_connector({"NARUON_SESSION_TOKEN": "session"})


def test_connector_requires_session_token():
    with pytest.raises(connector_main.ConnectorConfigError):
        connector_main.build_connector({"NARUON_REGISTRATION_TOKEN": "runner-token"})


def test_connector_builds_default_runner_ws_url_without_token_bearer_mixup():
    connector = connector_main.build_connector(
        {
            "NARUON_REGISTRATION_TOKEN": "runner token",
            "NARUON_SESSION_TOKEN": "session-token",
        }
    )

    assert connector.target_ws_url == "wss://naruon.net/ws/runner/runner%20token"
    assert connector.token == "session-token"


def test_connector_builds_configured_runner_ws_url():
    connector = connector_main.build_connector(
        {
            "NARUON_CONTROL_PLANE_WS_URL": (
                "wss://cp.example/ws/runner/{registration_token}"
            ),
            "NARUON_REGISTRATION_TOKEN": "runner/token",
            "NARUON_SESSION_TOKEN": "session-token",
        }
    )

    assert connector.target_ws_url == "wss://cp.example/ws/runner/runner%2Ftoken"


def test_runner_ws_log_url_redacts_path_token():
    assert (
        _log_safe_ws_url("wss://cp.example/ws/runner/nrn_secret-token?debug=token")
        == "wss://cp.example/ws/runner/[redacted]"
    )


@pytest.mark.asyncio
async def test_packaged_connector_fails_closed_without_local_adapters():
    connector = SelfHostedConnector(
        "wss://cp.example/ws/runner/nrn_registered-token",
        "session-token",
    )
    connector.send_response = AsyncMock()

    await connector.handle_message(
        json.dumps({"action": "send_smtp", "account": "mailbox-1"})
    )

    connector.send_response.assert_awaited_once_with(
        {
            "status": "error",
            "action": "send_smtp",
            "protocol": "SMTP",
            "account": "mailbox-1",
            "request_id": None,
            "provider_write_executed": False,
            "error": "adapter_not_configured",
        }
    )
