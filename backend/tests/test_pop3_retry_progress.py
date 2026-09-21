import datetime
import poplib
from unittest.mock import MagicMock

from db.models import TenantConfig
from services.pop3_worker import (
    Pop3CollectionProgressState,
    Pop3MessageIdentity,
    Pop3SyncWorker,
)


def _identities(count: int = 12) -> list[Pop3MessageIdentity]:
    return [
        Pop3MessageIdentity(message_number=number, provider_uidl=f"uid-{number}")
        for number in range(1, count + 1)
    ]


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


def test_uidl_selection_prioritizes_never_attempted_backlog_before_due_retries():
    worker = Pop3SyncWorker()
    now = datetime.datetime(2026, 9, 17, 10, 40, tzinfo=datetime.timezone.utc)
    progress = {
        f"uid-{number}": Pop3CollectionProgressState(
            disposition="retryable",
            retry_after=now - datetime.timedelta(minutes=1),
        )
        for number in range(3, 13)
    }

    selected = worker._select_uidl_candidates(_identities(), progress, now)

    assert [identity.provider_uidl for identity in selected[:2]] == ["uid-2", "uid-1"]
    assert len(selected) == 10


def test_uidl_selection_defers_retryable_identity_until_retry_after():
    worker = Pop3SyncWorker()
    now = datetime.datetime(2026, 9, 17, 10, 40, tzinfo=datetime.timezone.utc)
    progress = {
        "uid-12": Pop3CollectionProgressState(
            disposition="retryable",
            retry_after=now + datetime.timedelta(minutes=5),
        )
    }

    selected = worker._select_uidl_candidates(_identities(), progress, now)

    assert "uid-12" not in {identity.provider_uidl for identity in selected}
    assert [identity.provider_uidl for identity in selected[:2]] == ["uid-11", "uid-10"]


def test_uidl_selection_never_retries_observed_identity():
    worker = Pop3SyncWorker()
    now = datetime.datetime(2026, 9, 17, 10, 40, tzinfo=datetime.timezone.utc)
    progress = {
        "uid-12": Pop3CollectionProgressState(
            disposition="observed",
            retry_after=None,
        )
    }

    selected = worker._select_uidl_candidates(_identities(), progress, now)

    assert "uid-12" not in {identity.provider_uidl for identity in selected}


def test_persistent_negative_tail_becomes_retryable_without_hiding_lower_backlog(monkeypatch):
    worker = Pop3SyncWorker()
    client = MagicMock()
    client.uidl.return_value = (
        b"+OK",
        [f"{number} uid-{number}".encode() for number in range(1, 13)],
        192,
    )
    client.retr.side_effect = poplib.error_proto("-ERR no such message")
    monkeypatch.setattr("services.pop3_worker.poplib.POP3_SSL", lambda host, port: client)

    first_batch = worker._do_pop3_sync_batch(
        _config(),
        "pop3.example.com",
        995,
        collection_progress={},
    )

    assert first_batch.messages == []
    assert first_batch.retryable_uidls == frozenset(
        f"uid-{number}" for number in range(3, 13)
    )

    now = datetime.datetime(2026, 9, 17, 10, 40, tzinfo=datetime.timezone.utc)
    persisted_retry_state = {
        provider_uidl: Pop3CollectionProgressState(
            disposition="retryable",
            retry_after=now + datetime.timedelta(minutes=1),
        )
        for provider_uidl in first_batch.retryable_uidls
    }
    next_selected = worker._select_uidl_candidates(
        _identities(),
        persisted_retry_state,
        now,
    )

    assert [identity.provider_uidl for identity in next_selected] == ["uid-2", "uid-1"]
