import datetime

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
