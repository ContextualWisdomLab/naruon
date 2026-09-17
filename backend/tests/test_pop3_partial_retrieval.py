import poplib
from unittest.mock import MagicMock

from db.models import TenantConfig
from services.pop3_worker import Pop3SyncWorker


def _config() -> TenantConfig:
    return TenantConfig(
        user_id="pop3-user",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user@example.com",
        pop3_password="pop3-secret",
    )


def test_pop3_transport_failure_preserves_already_retrieved_uidl_messages(monkeypatch):
    worker = Pop3SyncWorker()
    config = _config()
    client = MagicMock()
    client.uidl.return_value = (b"+OK", [b"1 uid-1", b"2 uid-2"], 32)
    client.retr.side_effect = [
        (b"+OK", [b"Message-ID: <one@example.com>", b"", b"Body one"], 128),
        OSError("transport failed"),
    ]
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        config,
        "pop3.example.com",
        995,
        observed_uidls=set(),
    )

    assert len(messages) == 1
    assert messages[0].provider_uidl == "uid-1"
    assert b"<one@example.com>" in messages[0].source_content
    assert [entry.args[0] for entry in client.retr.call_args_list] == [1, 2]


def test_pop3_negative_retr_skips_failed_uidl_and_continues_same_session(monkeypatch):
    worker = Pop3SyncWorker()
    config = _config()
    client = MagicMock()
    client.uidl.return_value = (
        b"+OK",
        [b"1 uid-1", b"2 uid-2", b"3 uid-3"],
        48,
    )
    client.retr.side_effect = [
        (b"+OK", [b"Message-ID: <one@example.com>", b"", b"Body one"], 128),
        poplib.error_proto("-ERR no such message"),
        (b"+OK", [b"Message-ID: <three@example.com>", b"", b"Body three"], 128),
    ]
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        config,
        "pop3.example.com",
        995,
        observed_uidls=set(),
    )

    assert [message.provider_uidl for message in messages] == ["uid-1", "uid-3"]
    assert [entry.args[0] for entry in client.retr.call_args_list] == [1, 2, 3]


def test_pop3_fallback_negative_retr_continues_bounded_window(monkeypatch):
    worker = Pop3SyncWorker()
    config = _config()
    client = MagicMock()
    client.uidl.side_effect = poplib.error_proto("-ERR UIDL unsupported")
    client.list.return_value = (b"+OK", [b"1 100", b"2 100", b"3 100"], 300)
    client.retr.side_effect = [
        (b"+OK", [b"Message-ID: <one@example.com>", b"", b"Body one"], 128),
        poplib.error_proto("-ERR no such message"),
        (b"+OK", [b"Message-ID: <three@example.com>", b"", b"Body three"], 128),
    ]
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        config,
        "pop3.example.com",
        995,
        observed_uidls=set(),
    )

    assert [message.provider_uidl for message in messages] == [None, None]
    assert [entry.args[0] for entry in client.retr.call_args_list] == [1, 2, 3]


def test_pop3_malformed_protocol_response_stops_remaining_retrievals(monkeypatch):
    worker = Pop3SyncWorker()
    config = _config()
    client = MagicMock()
    client.uidl.return_value = (
        b"+OK",
        [b"1 uid-1", b"2 uid-2", b"3 uid-3"],
        48,
    )
    client.retr.side_effect = [
        (b"+OK", [b"Message-ID: <one@example.com>", b"", b"Body one"], 128),
        poplib.error_proto("unexpected response"),
        (b"+OK", [b"Message-ID: <three@example.com>", b"", b"Body three"], 128),
    ]
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    messages = worker._do_pop3_sync(
        config,
        "pop3.example.com",
        995,
        observed_uidls=set(),
    )

    assert [message.provider_uidl for message in messages] == ["uid-1"]
    assert [entry.args[0] for entry in client.retr.call_args_list] == [1, 2]
