import asyncio
import datetime
from types import SimpleNamespace

import pytest

from api.auth import AuthContext
from db.models import EmailSendRateBucket, SecurityAuditEvent
from services.email_send_rate_limiter import (
    EmailSendRateLimitUnavailable,
    enforce_send_email_rate_limit,
    rate_limit_scope_hash,
)


class _Result:
    def __init__(self, row=None):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class _SharedBucketStore:
    def __init__(self):
        self.buckets = {}
        self.lock = asyncio.Lock()


class _PostgresSession:
    def __init__(self, store):
        self.store = store
        self.added = []
        self.queries = []
        self.lock_held = False

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def execute(self, query, params=None):
        query_text = str(query).lower()
        self.queries.append(query_text)
        if "pg_advisory_xact_lock" in query_text:
            await self.store.lock.acquire()
            self.lock_held = True
            return _Result()
        if "email_send_rate_buckets" in query_text:
            scope_hash = next(
                value
                for key, value in query.compile().params.items()
                if "bucket_scope_hash" in key
            )
            return _Result(self.store.buckets.get(scope_hash))
        raise AssertionError(f"unexpected query: {query_text}")

    def add(self, item):
        self.added.append(item)
        if isinstance(item, EmailSendRateBucket):
            self.store.buckets[item.bucket_scope_hash] = item

    async def commit(self):
        if self.lock_held:
            self.store.lock.release()
            self.lock_held = False

    async def rollback(self):
        if self.lock_held:
            self.store.lock.release()
            self.lock_held = False


def _context(user_id="user-1", organization_id="org-1"):
    return AuthContext(
        user_id=user_id,
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id=f"workspace-{organization_id or user_id}",
    )


@pytest.mark.asyncio
async def test_shared_bucket_limits_concurrent_workers_without_cross_scope_leakage():
    store = _SharedBucketStore()
    observed_at = datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc)

    async def attempt(user_id):
        return await enforce_send_email_rate_limit(
            _PostgresSession(store), _context(user_id), now=observed_at
        )

    same_scope = await asyncio.gather(*(attempt("user-1") for _ in range(11)))
    other_scope = await asyncio.gather(*(attempt("user-2") for _ in range(10)))

    assert sum(decision.allowed for decision in same_scope) == 10
    assert sum(not decision.allowed for decision in same_scope) == 1
    assert all(decision.allowed for decision in other_scope)

    rollover = await enforce_send_email_rate_limit(
        _PostgresSession(store),
        _context("user-1"),
        now=observed_at + datetime.timedelta(seconds=61),
    )
    assert rollover.allowed is True
    assert store.buckets[rate_limit_scope_hash("user-1", "org-1")].attempt_count == 1


@pytest.mark.asyncio
async def test_shared_bucket_uses_transaction_lock_and_non_sensitive_audit_state():
    store = _SharedBucketStore()
    session = _PostgresSession(store)
    decision = await enforce_send_email_rate_limit(
        session,
        _context(),
        now=datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc),
    )

    assert decision.allowed is True
    assert any("pg_advisory_xact_lock" in query for query in session.queries)
    assert any("for update" in query for query in session.queries)
    bucket = next(item for item in session.added if isinstance(item, EmailSendRateBucket))
    audit = next(item for item in session.added if isinstance(item, SecurityAuditEvent))
    assert bucket.bucket_scope_hash == rate_limit_scope_hash("user-1", "org-1")
    assert "user-1" not in repr(bucket)
    assert "org-1" not in repr(bucket)
    assert "user-1" not in repr(audit)
    assert "org-1" not in repr(audit)
    assert audit.event_action == "email_send_rate_limit.allowed"


@pytest.mark.asyncio
async def test_rate_limiter_fails_closed_when_shared_state_is_unavailable():
    class _UnavailableSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    with pytest.raises(EmailSendRateLimitUnavailable):
        await enforce_send_email_rate_limit(_UnavailableSession(), _context())
