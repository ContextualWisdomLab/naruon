import asyncio
import pytest
from unittest.mock import MagicMock, patch

from db.models import TenantConfig
from services.pop3_worker import Pop3SyncWorker


def test_pop3_sync_requires_credentials(caplog, monkeypatch):
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="pop3.example.com",
        pop3_port=995,
    )
    pop3_client = MagicMock()

    monkeypatch.setattr(
        "services.pop3_worker.validate_pop3_destination",
        lambda host, port: (host, port),
    )
    with patch("services.pop3_worker.poplib.POP3_SSL", return_value=pop3_client):
        with pytest.raises(RuntimeError, match="POP3 account configuration incomplete"):
            worker._do_pop3_sync(config)

    pop3_client.user.assert_not_called()
    pop3_client.pass_.assert_not_called()
    pop3_client.quit.assert_called_once()
    assert "pop3_password" not in caplog.text
    assert "pop3-secret" not in caplog.text
    assert "credential secret" not in caplog.text.lower()


def test_pop3_sync_missing_secret_avoids_sensitive_log_names(caplog, monkeypatch):
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user",
    )
    pop3_client = MagicMock()

    monkeypatch.setattr(
        "services.pop3_worker.validate_pop3_destination",
        lambda host, port: (host, port),
    )
    with patch("services.pop3_worker.poplib.POP3_SSL", return_value=pop3_client):
        with pytest.raises(RuntimeError, match="POP3 account configuration incomplete"):
            worker._do_pop3_sync(config)

    pop3_client.user.assert_not_called()
    pop3_client.pass_.assert_not_called()
    pop3_client.quit.assert_called_once()
    assert "pop3_password" not in caplog.text
    assert "password" not in caplog.text.lower()
    assert "credential secret" not in caplog.text.lower()


def test_pop3_do_sync_validates_destination_before_connect():
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="127.0.0.1",
        pop3_port=995,
    )

    with patch("services.pop3_worker.poplib.POP3_SSL") as pop3_ssl:
        with pytest.raises(ValueError):
            worker._do_pop3_sync(config)

    pop3_ssl.assert_not_called()


@pytest.mark.asyncio
async def test_pop3_worker_skips_disallowed_destination():
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="127.0.0.1",
        pop3_port=995,
    )

    with patch("services.pop3_worker.poplib.POP3_SSL") as pop3_ssl:
        await worker._sync_tenant(config, asyncio.Semaphore(1))

    pop3_ssl.assert_not_called()


@pytest.mark.asyncio
async def test_pop3_worker_imports_retrieved_messages(monkeypatch):
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        organization_id="org-pop3",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user@example.com",
        pop3_password="pop3-secret",
    )
    raw_message = (
        b"Message-ID: <pop3-1@example.com>\r\n"
        b"From: Sender <sender@example.com>\r\n"
        b"To: pop3-user@example.com\r\n"
        b"Subject: POP3 import\r\n"
        b"Date: Mon, 15 Jun 2026 10:00:00 +0000\r\n"
        b"\r\n"
        b"Imported from POP3.\r\n"
    )
    pop3_client = MagicMock()
    pop3_client.list.return_value = (b"+OK", [b"1 128"], 128)
    pop3_client.retr.return_value = (b"+OK", raw_message.splitlines(), len(raw_message))
    imported: list[dict[str, object]] = []

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.rolled_back = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def commit(self):
            self.committed = True

        async def rollback(self):
            self.rolled_back = True

    session = FakeSession()

    async def fake_process_fetched_email(
        db_session,
        email_data,
        user_id,
        organization_id,
        owner_addresses=None,
        source_content=None,
    ):
        imported.append(
            {
                "session": db_session,
                "email_data": email_data,
                "user_id": user_id,
                "organization_id": organization_id,
                "owner_addresses": owner_addresses,
                "source_content": source_content,
            }
        )

    monkeypatch.setattr(
        "services.pop3_worker.validate_pop3_destination",
        lambda host, port: (host, port),
    )
    monkeypatch.setattr(
        "services.pop3_worker.AsyncSessionLocal",
        lambda: session,
    )
    monkeypatch.setattr(
        "services.pop3_worker.process_fetched_email",
        fake_process_fetched_email,
        raising=False,
    )
    monkeypatch.setattr(
        "services.pop3_worker.poplib.POP3_SSL",
        lambda host, port: pop3_client,
    )

    await worker._sync_tenant(config, asyncio.Semaphore(1))

    pop3_client.user.assert_called_once_with("pop3-user@example.com")
    pop3_client.pass_.assert_called_once_with("pop3-secret")
    pop3_client.list.assert_called_once()
    pop3_client.retr.assert_called_once_with(1)
    pop3_client.quit.assert_called_once()
    assert len(imported) == 1
    assert imported[0]["session"] is session
    assert imported[0]["user_id"] == "pop3-user"
    assert imported[0]["organization_id"] == "org-pop3"
    assert imported[0]["owner_addresses"] == ["pop3-user@example.com"]
    assert imported[0]["source_content"] == raw_message
    assert imported[0]["email_data"]["message_id"] == "<pop3-1@example.com>"
    assert imported[0]["email_data"]["subject"] == "POP3 import"
    assert session.committed is True
    assert session.rolled_back is False
