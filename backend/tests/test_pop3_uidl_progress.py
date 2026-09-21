import poplib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db.models import TenantConfig
from services.pop3_worker import Pop3RetrievedMessage, Pop3SyncWorker


def _config() -> TenantConfig:
    return TenantConfig(
        id=42,
        user_id="pop3-user",
        organization_id="org-pop3",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user@example.com",
        pop3_password="pop3-secret",
    )


def _client_with_uidls(count: int = 12) -> MagicMock:
    client = MagicMock()
    client.uidl.return_value = (
        b"+OK",
        [f"{message_number} uid-{message_number}".encode() for message_number in range(1, count + 1)],
        count * 16,
    )
    client.list.return_value = (
        b"+OK",
        [f"{message_number} 128".encode() for message_number in range(1, count + 1)],
        count * 128,
    )
    client.retr.side_effect = lambda message_number: (
        b"+OK",
        [f"Message-ID: <pop3-{message_number}@example.com>".encode(), b"", b"Body"],
        128,
    )
    return client


def test_pop3_uidl_progress_selects_older_unseen_after_newer_window(monkeypatch):
    worker = Pop3SyncWorker()
    client = _client_with_uidls()
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    observed_uidls = {f"uid-{message_number}" for message_number in range(3, 13)}
    messages = worker._do_pop3_sync(
        _config(),
        "pop3.example.com",
        995,
        observed_uidls=observed_uidls,
    )

    assert [entry.args[0] for entry in client.retr.call_args_list] == [1, 2]
    assert [message.provider_uidl for message in messages] == ["uid-1", "uid-2"]


def test_pop3_uidl_progress_uses_current_session_number_after_renumbering(monkeypatch):
    worker = Pop3SyncWorker()
    client = MagicMock()
    client.uidl.return_value = (
        b"+OK",
        [b"1 uid-old-2", b"2 uid-old-3", b"3 uid-new-4"],
        48,
    )
    client.list.return_value = (b"+OK", [b"1 128", b"2 128", b"3 128"], 384)
    client.retr.side_effect = lambda message_number: (
        b"+OK",
        [f"Message-ID: <renumber-{message_number}@example.com>".encode(), b"", b"Body"],
        128,
    )
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        _config(),
        "pop3.example.com",
        995,
        observed_uidls={"uid-old-2", "uid-old-3"},
    )

    client.retr.assert_called_once_with(3)
    assert messages[0].provider_uidl == "uid-new-4"


def test_pop3_uidl_unsupported_falls_back_without_claiming_durable_identity(monkeypatch):
    worker = Pop3SyncWorker()
    client = _client_with_uidls()
    client.uidl.side_effect = poplib.error_proto("-ERR UIDL unsupported")
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        _config(),
        "pop3.example.com",
        995,
        observed_uidls={"uid-3"},
    )

    assert [entry.args[0] for entry in client.retr.call_args_list] == list(range(3, 13))
    assert all(message.provider_uidl is None for message in messages)


@pytest.mark.asyncio
async def test_import_records_uidl_after_successful_persistence(monkeypatch):
    worker = Pop3SyncWorker()
    config = _config()
    raw_message = (
        b"Message-ID: <uidl-progress@example.com>\r\n"
        b"From: Sender <sender@example.com>\r\n"
        b"To: pop3-user@example.com\r\n"
        b"Subject: UIDL progress\r\n"
        b"Date: Mon, 15 Jun 2026 10:00:00 +0000\r\n\r\nBody\r\n"
    )
    executed = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, statement):
            executed.append(statement)
            return SimpleNamespace()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def fake_persist(*args, **kwargs):
        return SimpleNamespace(created_record=True)

    monkeypatch.setattr("services.pop3_worker.AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr("services.pop3_worker.persist_fetched_email", fake_persist)

    imported_count = await worker._import_messages(
        config,
        [Pop3RetrievedMessage(source_content=raw_message, provider_uidl="uid-1")],
    )

    assert imported_count == 1
    assert len(executed) == 1
    compiled = str(executed[0].compile(compile_kwargs={"literal_binds": True}))
    assert "pop3_observed_messages" in compiled
    assert "uid-1" in compiled
