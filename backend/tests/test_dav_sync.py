from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_webdav_source_label_uses_opaque_source_id():
    from services.webdav_service import safe_webdav_source_label

    assert (
        safe_webdav_source_label("webdav_src_primary")
        == "WebDAV source webdav_src_primary"
    )
    assert safe_webdav_source_label(None) == "WebDAV source"


@pytest.mark.asyncio
async def test_caldav_event_parsing_and_sync():
    from services.caldav_service import sync_caldav_accounts

    session_mock = AsyncMock()
    account_mock = MagicMock()
    account_mock.id = 1
    account_mock.server_url = "https://alice:secret@caldav.example.com/calendars"
    account_mock.username = "user"
    account_mock.credentials_encrypted = "pass"

    execute_res = MagicMock()
    execute_res.scalars.return_value.all.return_value = [account_mock]
    session_mock.execute.return_value = execute_res

    with patch("services.caldav_service.logger") as logger_mock:
        synced = await sync_caldav_accounts(session_mock, "user_1")

        assert synced is False
        logger_mock.warning.assert_called_once()
        warning_args = logger_mock.warning.call_args.args
        assert "inbound CalDAV import adapter is not configured" in warning_args[0]
        logged_url = warning_args[2]
        assert logged_url == "https://caldav.example.com/calendars"
        assert "secret" not in logged_url


def test_webdav_service_has_no_demo_backing_store_or_noop_write_api():
    from services.webdav_service import WebDavService

    service = WebDavService()
    forbidden_attributes = {
        "_mock_accounts",
        "_mock_folders",
        "get_connected_accounts",
        "get_project_folders",
        "sync_attachments_to_folder",
        "determine_webdav_writeback_intent",
    }

    assert forbidden_attributes.isdisjoint(dir(service))


def test_webdav_runtime_module_has_no_success_shaped_fake_sync():
    from services import webdav_service as module

    assert not hasattr(module, "sync_webdav_folders")
