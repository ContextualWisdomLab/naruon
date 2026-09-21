import datetime
import poplib
from unittest.mock import MagicMock

import pytest

from db.models import TenantConfig
from services.pop3_worker import (
    Pop3CollectionProgressState,
    Pop3MessageIdentity,
    Pop3SyncWorker,
)


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


def _identities() -> list[Pop3MessageIdentity]:
    return [
        Pop3MessageIdentity(message_number=number, provider_uidl=f"uid-{number}")
        for number in range(1, 13)
    ]


@pytest.mark.parametrize(
    "failure",
    [
        poplib.error_proto("unexpected response"),
        OSError("transport failed"),
    ],
)
def test_interrupted_retr_marks_attempted_uidl_retryable_before_stopping(failure):
    worker = Pop3SyncWorker()
    client = MagicMock()
    selected = list(reversed(_identities()))[:10]
    client.retr.side_effect = failure

    batch = worker._retrieve_uidl_batch(client, _config(), selected)

    assert batch.messages == []
    assert batch.retryable_uidls == frozenset({"uid-12"})
    client.retr.assert_called_once_with(12)


def test_interrupted_retr_does_not_keep_failed_tail_fresh_on_next_poll():
    worker = Pop3SyncWorker()
    client = MagicMock()
    selected = list(reversed(_identities()))[:10]
    client.retr.side_effect = OSError("transport failed")

    first_batch = worker._retrieve_uidl_batch(client, _config(), selected)

    now = datetime.datetime(2026, 9, 22, 2, 0, tzinfo=datetime.timezone.utc)
    progress = {
        uidl: Pop3CollectionProgressState(
            disposition="retryable",
            retry_after=now + datetime.timedelta(minutes=1),
        )
        for uidl in first_batch.retryable_uidls
    }
    next_selected = worker._select_uidl_candidates(_identities(), progress, now)

    assert "uid-12" not in {identity.provider_uidl for identity in next_selected}
    assert [identity.provider_uidl for identity in next_selected[:2]] == [
        "uid-11",
        "uid-10",
    ]
