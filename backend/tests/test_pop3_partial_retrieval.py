import poplib
from unittest.mock import MagicMock

from db.models import TenantConfig
from services.pop3_worker import Pop3SyncWorker


def test_pop3_retr_failure_preserves_already_retrieved_uidl_messages(monkeypatch):
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user@example.com",
        pop3_password="pop3-secret",
    )
    client = MagicMock()
    client.uidl.return_value = (b"+OK", [b"1 uid-1", b"2 uid-2"], 32)
    client.retr.side_effect = [
        (b"+OK", [b"Message-ID: <one@example.com>", b"", b"Body one"], 128),
        poplib.error_proto("-ERR retrieval failed"),
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
