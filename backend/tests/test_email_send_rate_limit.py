"""Acceptance tests for the shared email-send rate-limit authority.

These cases follow issue #1379: process-local dictionaries can be bypassed
across workers, so the limiter must share one atomic bucket per authorized
``(organization_id, owner_user_id)`` scope.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from threading import Lock

import pytest

from services.email_send_rate_limit import (
    DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS,
    DEFAULT_EMAIL_SEND_LIMIT_WINDOW_SECONDS,
    EmailSendLimitDecision,
    EmailSendLimitStoreUnavailable,
    EmailSendLimitWindowState,
    SharedMemoryEmailSendLimitStore,
    SqlAlchemyEmailSendLimitStore,
    decide_email_send_limit,
    normalize_organization_scope,
    reserve_email_send_attempt,
)

_FIXED_NOW = datetime(2026, 8, 16, 16, 0, tzinfo=timezone.utc)


def _allowed_state(
    *,
    organization_id: str,
    owner_user_id: str,
    attempt_count: int,
    window_started_at: datetime = _FIXED_NOW,
) -> EmailSendLimitWindowState:
    return EmailSendLimitWindowState(
        organization_id=organization_id,
        owner_user_id=owner_user_id,
        window_started_at=window_started_at,
        attempt_count=attempt_count,
    )


def test_independent_worker_buckets_oversubscribe_the_configured_limit() -> None:
    """RED evidence: two process-local stores each allow a full bucket."""
    worker_one = SharedMemoryEmailSendLimitStore()
    worker_two = SharedMemoryEmailSendLimitStore()

    async def _fill(store: SharedMemoryEmailSendLimitStore) -> int:
        allowed = 0
        for _ in range(DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS):
            decision = await reserve_email_send_attempt(
                store,
                organization_id="org-acme",
                owner_user_id="mail-owner",
                observed_at=_FIXED_NOW,
            )
            if decision.decision_code == "allowed":
                allowed += 1
        return allowed

    assert asyncio.run(_fill(worker_one)) == DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS
    assert asyncio.run(_fill(worker_two)) == DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS


def test_shared_store_rejects_the_eleventh_attempt_in_one_window() -> None:
    store = SharedMemoryEmailSendLimitStore()

    async def _run() -> list[str]:
        codes: list[str] = []
        for _ in range(DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS + 1):
            decision = await reserve_email_send_attempt(
                store,
                organization_id="org-acme",
                owner_user_id="mail-owner",
                observed_at=_FIXED_NOW,
            )
            codes.append(decision.decision_code)
        return codes

    codes = asyncio.run(_run())
    assert codes[:10] == ["allowed"] * 10
    assert codes[10] == "blocked"
    assert codes[10] != "unavailable"


def test_two_workers_sharing_one_store_share_the_same_bucket() -> None:
    shared_buckets: dict[tuple[str, str], EmailSendLimitWindowState] = {}
    shared_lock = Lock()
    worker_one = SharedMemoryEmailSendLimitStore(
        windows=shared_buckets,
        lock=shared_lock,
    )
    worker_two = SharedMemoryEmailSendLimitStore(
        windows=shared_buckets,
        lock=shared_lock,
    )

    async def _run() -> tuple[int, int]:
        allowed = 0
        blocked = 0
        for index in range(DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS + 4):
            store = worker_one if index % 2 == 0 else worker_two
            decision = await reserve_email_send_attempt(
                store,
                organization_id="org-acme",
                owner_user_id="mail-owner",
                observed_at=_FIXED_NOW,
            )
            if decision.decision_code == "allowed":
                allowed += 1
            elif decision.decision_code == "blocked":
                blocked += 1
        return allowed, blocked

    allowed, blocked = asyncio.run(_run())
    assert allowed == DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS
    assert blocked == 4


def test_concurrent_reservations_cannot_oversubscribe_the_bucket() -> None:
    store = SharedMemoryEmailSendLimitStore()

    async def _run() -> list[str]:
        decisions = await asyncio.gather(
            *[
                reserve_email_send_attempt(
                    store,
                    organization_id="org-acme",
                    owner_user_id="mail-owner",
                    observed_at=_FIXED_NOW,
                )
                for _ in range(20)
            ]
        )
        return [decision.decision_code for decision in decisions]

    codes = asyncio.run(_run())
    assert codes.count("allowed") == DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS
    assert codes.count("blocked") == 10
    assert "unavailable" not in codes


def test_distinct_users_and_organizations_stay_isolated() -> None:
    store = SharedMemoryEmailSendLimitStore()

    async def _allow(
        organization_id: str | None,
        owner_user_id: str,
    ) -> str:
        decision = await reserve_email_send_attempt(
            store,
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            observed_at=_FIXED_NOW,
            max_attempts=1,
        )
        return decision.decision_code

    assert asyncio.run(_allow("org-acme", "owner-a")) == "allowed"
    assert asyncio.run(_allow("org-acme", "owner-b")) == "allowed"
    assert asyncio.run(_allow("org-beta", "owner-a")) == "allowed"
    assert asyncio.run(_allow(None, "owner-a")) == "allowed"
    assert asyncio.run(_allow("org-acme", "owner-a")) == "blocked"


def test_window_rollover_uses_injected_clock_not_sleep() -> None:
    store = SharedMemoryEmailSendLimitStore()

    async def _run() -> tuple[str, str]:
        opened = await reserve_email_send_attempt(
            store,
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW,
            max_attempts=1,
        )
        assert opened.decision_code == "allowed"
        still_inside = await reserve_email_send_attempt(
            store,
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW + timedelta(seconds=59),
            max_attempts=1,
        )
        rolled = await reserve_email_send_attempt(
            store,
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW + timedelta(seconds=60),
            max_attempts=1,
        )
        return still_inside.decision_code, rolled.decision_code

    still_inside, rolled = asyncio.run(_run())
    assert still_inside == "blocked"
    assert rolled == "allowed"


def test_shared_store_failure_is_unavailable_not_local_memory() -> None:
    class _UnavailableStore:
        async def reserve_attempt(
            self,
            *,
            organization_id: str | None,
            owner_user_id: str,
            observed_at: datetime,
            max_attempts: int,
            window_seconds: float,
        ) -> EmailSendLimitDecision:
            raise EmailSendLimitStoreUnavailable("shared send-limit state unavailable")

    decision = asyncio.run(
        reserve_email_send_attempt(
            _UnavailableStore(),
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW,
        )
    )
    assert decision.decision_code == "unavailable"
    assert decision.error_code == "email_send_limit_unavailable"
    assert decision.http_status_code == 503
    assert "rate limit exceeded" not in decision.user_message.lower()


def test_limiter_state_does_not_persist_message_content() -> None:
    store = SharedMemoryEmailSendLimitStore()
    decision = asyncio.run(
        reserve_email_send_attempt(
            store,
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW,
        )
    )
    snapshot = store.persisted_state()
    serialized = repr(snapshot) + repr(decision)
    for forbidden in (
        "Quarter plan",
        "This is a reply.",
        "test@example.com",
        "smtp_password",
        "subject",
        "body",
        "to_address",
    ):
        assert forbidden not in serialized
    assert set(decision.__dataclass_fields__) == {
        "decision_code",
        "error_code",
        "http_status_code",
        "user_message",
        "organization_scope",
        "owner_user_id",
        "attempt_count",
        "window_started_at",
    }


def test_decide_email_send_limit_resets_expired_window() -> None:
    previous = _allowed_state(
        organization_id="org-acme",
        owner_user_id="mail-owner",
        attempt_count=10,
        window_started_at=_FIXED_NOW - timedelta(seconds=60),
    )
    decision, next_state = decide_email_send_limit(
        previous,
        observed_at=_FIXED_NOW,
        max_attempts=10,
        window_seconds=DEFAULT_EMAIL_SEND_LIMIT_WINDOW_SECONDS,
    )
    assert decision == "allowed"
    assert next_state is not None
    assert next_state.attempt_count == 1
    assert next_state.window_started_at == _FIXED_NOW


def test_normalize_organization_scope_keeps_missing_org_distinct() -> None:
    assert normalize_organization_scope(None) == ""
    assert normalize_organization_scope("org-acme") == "org-acme"


@pytest.mark.asyncio
async def test_sqlalchemy_store_maps_execute_failure_to_unavailable() -> None:
    class _BrokenSession:
        async def execute(self, _statement):
            raise RuntimeError("connection refused")

    store = SqlAlchemyEmailSendLimitStore(_BrokenSession())
    with pytest.raises(EmailSendLimitStoreUnavailable):
        await store.reserve_attempt(
            organization_id="org-acme",
            owner_user_id="mail-owner",
            observed_at=_FIXED_NOW,
            max_attempts=10,
            window_seconds=60.0,
        )


@pytest.mark.asyncio
async def test_sqlalchemy_reservation_statement_has_no_message_fields() -> None:
    statement = SqlAlchemyEmailSendLimitStore.reservation_statement(
        organization_id="org-acme",
        owner_user_id="mail-owner",
        observed_at=_FIXED_NOW,
        max_attempts=10,
        window_seconds=60.0,
    )
    compiled = str(statement)
    for forbidden in ("subject", "body", "to_address", "recipients", "smtp_password"):
        assert forbidden not in compiled
    assert "email_send_limit_windows" in compiled
    assert "attempt_count" in compiled
