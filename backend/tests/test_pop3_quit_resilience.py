import poplib
from unittest.mock import MagicMock

from db.models import TenantConfig
from services.pop3_worker import Pop3SyncWorker


def test_pop3_quit_failure_does_not_discard_retrieved_messages(monkeypatch):
    worker = Pop3SyncWorker()
    config = TenantConfig(
        user_id="pop3-user",
        pop3_server="pop3.example.com",
        pop3_port=995,
        pop3_username="pop3-user@example.com",
        pop3_password="pop3-secret",
    )
    raw_lines = [b"Message-ID: <pop3-1@example.com>", b"", b"Body"]
    pop3_client = MagicMock()
    pop3_client.list.return_value = (b"+OK", [b"1 128"], 128)
    pop3_client.retr.return_value = (b"+OK", raw_lines, 128)
    pop3_client.quit.side_effect = poplib.error_proto("-ERR connection already closed")

    monkeypatch.setattr(
        "services.pop3_worker.validate_pop3_destination",
        lambda host, port: (host, port),
    )
    monkeypatch.setattr(
        "services.pop3_worker.poplib.POP3_SSL",
        lambda host, port: pop3_client,
    )

    messages = worker._do_pop3_sync(config)

    assert messages == [b"Message-ID: <pop3-1@example.com>\r\n\r\nBody\r\n"]
    pop3_client.quit.assert_called_once()
