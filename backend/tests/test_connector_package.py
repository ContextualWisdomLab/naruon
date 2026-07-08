import json
import runpy
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


def test_connector_module_entrypoint_fails_closed_without_required_env(monkeypatch):
    monkeypatch.delenv("NARUON_REGISTRATION_TOKEN", raising=False)
    monkeypatch.delenv("NARUON_SESSION_TOKEN", raising=False)
    monkeypatch.delitem(sys.modules, "connector.main", raising=False)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("connector.main", run_name="__main__")

    assert exc.value.code == 2


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


@pytest.mark.asyncio
async def test_packaged_connector_dispatches_carddav_to_handler():
    from unittest.mock import AsyncMock

    handler = AsyncMock(
        return_value={"status": "success", "provider_write_executed": True}
    )
    connector = SelfHostedConnector(
        "wss://cp.example/ws/runner/nrn_registered-token",
        "session-token",
        carddav_write_handler=handler,
    )
    connector.send_response = AsyncMock()

    await connector.handle_message(
        json.dumps(
            {
                "action": "write_carddav",
                "account": "mailbox-1",
                "source_id": "carddav_src_1",
            }
        )
    )

    handler.assert_awaited_once()
    response = connector.send_response.await_args.args[0]
    assert response["action"] == "write_carddav"
    assert response["protocol"] == "CardDAV"
    assert response["status"] == "success"


@pytest.mark.asyncio
async def test_packaged_connector_carddav_fails_closed_without_adapter():
    from unittest.mock import AsyncMock

    connector = SelfHostedConnector(
        "wss://cp.example/ws/runner/nrn_registered-token",
        "session-token",
    )
    connector.send_response = AsyncMock()

    await connector.handle_message(
        json.dumps({"action": "write_carddav", "account": "mailbox-1"})
    )

    response = connector.send_response.await_args.args[0]
    assert response["error"] == "adapter_not_configured"
    assert response["protocol"] == "CardDAV"


def test_build_connector_accepts_seeded_handlers():
    from unittest.mock import AsyncMock

    handlers = {
        "imap_fetch_handler": AsyncMock(),
        "smtp_send_handler": AsyncMock(),
        "webdav_write_handler": AsyncMock(),
        "caldav_write_handler": AsyncMock(),
        "carddav_write_handler": AsyncMock(),
    }
    connector = connector_main.build_connector(
        {
            "NARUON_REGISTRATION_TOKEN": "runner-token",
            "NARUON_SESSION_TOKEN": "session-token",
        },
        handlers=handlers,
    )
    assert connector.carddav_write_handler is handlers["carddav_write_handler"]
    assert connector.imap_fetch_handler is handlers["imap_fetch_handler"]
