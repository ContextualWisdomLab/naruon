import asyncio
import datetime
from types import SimpleNamespace

import pytest

from api.auth import AuthContext
from db.models import SecurityAuditEvent
import services.email_send_rate_limiter as limiter_module
from services.email_send_rate_limiter import (
    EmailSendRateLimitUnavailable,
    enforce_send_email_rate_limit,
    rate_limit_scope_hash,
)


class _Result:
    def __init__(self, row=0):
        self.row = row

    def scalar_one(self):
        return self.row


class _SharedAttemptStore:
    def __init__(self):
        self.events = []
        self.lock = asyncio.Lock()


class _PostgresSession:
    def __init__(self, store):
        self.store = store
        self.added = []
        self.queries = []
        self.lock_held = False
        self.pending = []
        self.isolation_level = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        if self.lock_held:
            self.store.lock.release()
            self.lock_held = False

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def connection(self, *, execution_options):
        self.isolation_level = execution_options["isolation_level"]
        return self

    async def execute(self, query, params=None):
        query_text = str(query).lower()
        self.queries.append(query_text)
        if "pg_advisory_xact_lock" in query_text:
            await self.store.lock.acquire()
            self.lock_held = True
            return _Result()
        if "security_audit_events" in query_text:
            values = tuple(query.compile().params.values())
            resource_uid = next(value for value in values if str(value).startswith("email_send_scope:"))
            event_action = next(
                value
                for value in values
                if str(value).startswith("email_send_rate_limit.")
            )
            window_started_at = next(value for value in values if isinstance(value, datetime.datetime))
            return _Result(
                sum(
                    event.resource_uid == resource_uid
                    and event.event_action == event_action
                    and event.observed_at > window_started_at
                    for event in self.store.events
                )
            )
        raise AssertionError(f"unexpected query: {query_text}")

    def add(self, item):
        self.added.append(item)
        if isinstance(item, SecurityAuditEvent):
            self.pending.append(item)

    async def commit(self):
        self.store.events.extend(self.pending)
        self.pending.clear()
        if self.lock_held:
            self.store.lock.release()
            self.lock_held = False

    async def rollback(self):
        self.pending.clear()
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
async def test_sliding_window_limits_concurrent_workers_without_cross_scope_leakage(monkeypatch):
    store = _SharedAttemptStore()
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: _PostgresSession(store))
    observed_at = datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc)

    async def attempt(user_id):
        return await enforce_send_email_rate_limit(
            _context(user_id), now=observed_at
        )

    same_scope = await asyncio.gather(*(attempt("user-1") for _ in range(11)))
    other_scope = await asyncio.gather(*(attempt("user-2") for _ in range(10)))

    assert sum(decision.allowed for decision in same_scope) == 10
    assert sum(not decision.allowed for decision in same_scope) == 1
    assert all(decision.allowed for decision in other_scope)

    rollover = await enforce_send_email_rate_limit(
        _context("user-1"),
        now=observed_at + datetime.timedelta(seconds=61),
    )
    assert rollover.allowed is True
    scope_uid = f'email_send_scope:{rate_limit_scope_hash("user-1", "org-1")}'
    assert sum(event.resource_uid == scope_uid for event in store.events) == 12


@pytest.mark.asyncio
async def test_sliding_window_blocks_boundary_burst(monkeypatch):
    store = _SharedAttemptStore()
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: _PostgresSession(store))
    started_at = datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc)

    for offset_seconds in range(50, 60):
        decision = await enforce_send_email_rate_limit(
            _context(),
            now=started_at + datetime.timedelta(seconds=offset_seconds),
        )
        assert decision.allowed is True

    blocked = await enforce_send_email_rate_limit(
        _context(),
        now=started_at + datetime.timedelta(seconds=61),
    )
    assert blocked.allowed is False
    for offset_seconds in range(62, 72):
        assert not (
            await enforce_send_email_rate_limit(
                _context(),
                now=started_at + datetime.timedelta(seconds=offset_seconds),
            )
        ).allowed
    assert sum(
        event.event_action == "email_send_rate_limit.quota_exhausted"
        for event in store.events
    ) == 1


@pytest.mark.asyncio
async def test_limiter_uses_owned_transaction_and_non_sensitive_audit_state(monkeypatch):
    store = _SharedAttemptStore()
    session = _PostgresSession(store)
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: session)
    decision = await enforce_send_email_rate_limit(
        _context(),
        now=datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc),
    )

    assert decision.allowed is True
    assert any("pg_advisory_xact_lock" in query for query in session.queries)
    assert session.isolation_level == "READ COMMITTED"
    audit = next(item for item in session.added if isinstance(item, SecurityAuditEvent))
    assert "user-1" not in repr(audit)
    assert "org-1" not in repr(audit)
    assert audit.event_action == "email_send_rate_limit.allowed"


@pytest.mark.asyncio
async def test_rate_limiter_fails_closed_when_shared_state_is_unavailable():
    class _UnavailableSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    original_factory = limiter_module.AsyncSessionLocal
    limiter_module.AsyncSessionLocal = lambda: _UnavailableSession()
    try:
        with pytest.raises(EmailSendRateLimitUnavailable):
            await enforce_send_email_rate_limit(_context())
    finally:
        limiter_module.AsyncSessionLocal = original_factory


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_rate_limiter_real_postgres_reserves_and_denies(monkeypatch):
    from core.config import settings
    from asyncpg.exceptions import InvalidAuthorizationSpecificationError
    from asyncpg.exceptions import InvalidPasswordError
    from db.models import Base
    from sqlalchemy import delete, select
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            await connection.run_sync(Base.metadata.create_all)
    except (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
        OperationalError,
        OSError,
    ):
        await engine.dispose()
        pytest.skip("PostgreSQL smoke database unavailable")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(limiter_module, "SEND_RATE_LIMIT_MAX_ATTEMPTS", 1)
    context = _context("rate-limit-smoke-user", "rate-limit-smoke-org")
    scope_uid = (
        "email_send_scope:"
        f"{rate_limit_scope_hash(context.user_id, context.organization_id)}"
    )
    observed_at = datetime.datetime.now(datetime.timezone.utc)

    async def cleanup() -> None:
        async with session_factory() as session:
            await session.execute(
                delete(SecurityAuditEvent).where(
                    SecurityAuditEvent.resource_uid == scope_uid
                )
            )
            await session.commit()

    await cleanup()
    try:
        first = await enforce_send_email_rate_limit(context, now=observed_at)
        second = await enforce_send_email_rate_limit(context, now=observed_at)
        async with session_factory() as session:
            actions = (
                await session.execute(
                    select(SecurityAuditEvent.event_action)
                    .where(SecurityAuditEvent.resource_uid == scope_uid)
                    .order_by(SecurityAuditEvent.event_action)
                )
            ).scalars().all()
    finally:
        await cleanup()
        await engine.dispose()

    assert first.allowed is True
    assert second.allowed is False
    assert actions == [
        "email_send_rate_limit.allowed",
        "email_send_rate_limit.quota_exhausted",
    ]
