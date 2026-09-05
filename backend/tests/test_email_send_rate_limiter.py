import asyncio
import datetime
import uuid
from types import SimpleNamespace

import pytest

from api.auth import AuthContext
from db.models import SecurityAuditEvent
import services.email_send_rate_limiter as limiter_module


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
    def __init__(self, store, *, database_now: datetime.datetime | None = None):
        self.store = store
        self.added = []
        self.queries = []
        self.lock_held = False
        self.pending = []
        self.isolation_level = None
        self.database_now = database_now or datetime.datetime(
            2026, 8, 19, tzinfo=datetime.timezone.utc
        )

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
        if "clock_timestamp" in query_text:
            return _Result(self.database_now)
        if query_text.startswith("delete from security_audit_events"):
            values = tuple(query.compile().params.values())
            resource_uid = next(
                value
                for value in values
                if str(value).startswith("email_send_scope:")
            )
            event_action = next(
                value
                for value in values
                if str(value).startswith("email_send_rate_limit.")
            )
            cutoff = next(
                value for value in values if isinstance(value, datetime.datetime)
            )
            retained_events = [
                event
                for event in self.store.events
                if not (
                    event.resource_uid == resource_uid
                    and event.event_action == event_action
                    and event.observed_at <= cutoff
                )
            ]
            deleted_count = len(self.store.events) - len(retained_events)
            self.store.events = retained_events
            return _Result(deleted_count)
        if "security_audit_events" in query_text:
            values = tuple(query.compile().params.values())
            resource_uid = next(
                value
                for value in values
                if str(value).startswith("email_send_scope:")
            )
            event_action = next(
                value
                for value in values
                if str(value).startswith("email_send_rate_limit.")
            )
            window_started_at = next(
                value for value in values if isinstance(value, datetime.datetime)
            )
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


def _context(
    user_id="user-1", organization_id="org-1", workspace_id: str | None = None
):
    return AuthContext(
        user_id=user_id,
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id=workspace_id or f"workspace-{organization_id or user_id}",
    )


@pytest.mark.asyncio
async def test_sliding_window_limits_concurrent_workers_without_cross_scope_leakage(
    monkeypatch,
):
    store = _SharedAttemptStore()
    monkeypatch.setattr(
        limiter_module, "AsyncSessionLocal", lambda: _PostgresSession(store)
    )
    observed_at = datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc)

    async def attempt(user_id):
        return await limiter_module.enforce_send_email_rate_limit(
            _context(user_id), now=observed_at
        )

    same_scope = await asyncio.gather(*(attempt("user-1") for _ in range(11)))
    other_scope = await asyncio.gather(*(attempt("user-2") for _ in range(10)))
    other_workspace = await asyncio.gather(
        *(
            limiter_module.enforce_send_email_rate_limit(
                _context("user-1", workspace_id="workspace-2"), now=observed_at
            )
            for _ in range(10)
        )
    )

    assert sum(decision.allowed for decision in same_scope) == 10
    assert sum(not decision.allowed for decision in same_scope) == 1
    assert all(decision.allowed for decision in other_scope)
    assert all(decision.allowed for decision in other_workspace)

    rollover = await limiter_module.enforce_send_email_rate_limit(
        _context("user-1"),
        now=observed_at + datetime.timedelta(seconds=61),
    )
    assert rollover.allowed is True
    scope_uid = (
        "email_send_scope:"
        f'{limiter_module.rate_limit_scope_hash("user-1", "org-1", "workspace-org-1")}'
    )
    assert sum(event.resource_uid == scope_uid for event in store.events) == 2


@pytest.mark.asyncio
async def test_sliding_window_blocks_boundary_burst(monkeypatch):
    store = _SharedAttemptStore()
    monkeypatch.setattr(
        limiter_module, "AsyncSessionLocal", lambda: _PostgresSession(store)
    )
    started_at = datetime.datetime(2026, 8, 19, tzinfo=datetime.timezone.utc)

    for offset_seconds in range(50, 60):
        decision = await limiter_module.enforce_send_email_rate_limit(
            _context(),
            now=started_at + datetime.timedelta(seconds=offset_seconds),
        )
        assert decision.allowed is True

    blocked = await limiter_module.enforce_send_email_rate_limit(
        _context(),
        now=started_at + datetime.timedelta(seconds=61),
    )
    assert blocked.allowed is False
    for offset_seconds in range(62, 72):
        assert not (
            await limiter_module.enforce_send_email_rate_limit(
                _context(),
                now=started_at + datetime.timedelta(seconds=offset_seconds),
            )
        ).allowed
    assert sum(
        event.event_action == "email_send_rate_limit.quota_exhausted"
        for event in store.events
    ) == 1


@pytest.mark.asyncio
async def test_limiter_prunes_expired_allowed_state_but_keeps_denial_evidence(monkeypatch):
    store = _SharedAttemptStore()
    observed_at = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=datetime.timezone.utc)
    scope_hash = limiter_module.rate_limit_scope_hash(
        "user-1", "org-1", "workspace-org-1"
    )
    scope_uid = f"email_send_scope:{scope_hash}"
    expired_at = observed_at - datetime.timedelta(seconds=61)
    expired_allowed = SecurityAuditEvent(
        actor_user_id="user-1",
        actor_role="member",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        event_action="email_send_rate_limit.allowed",
        resource_type="email_send_rate_limit",
        resource_uid=scope_uid,
        evidence_source="services.email_send_rate_limiter",
        observed_at=expired_at,
    )
    durable_denial = SecurityAuditEvent(
        actor_user_id="user-1",
        actor_role="member",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        event_action="email_send_rate_limit.quota_exhausted",
        resource_type="email_send_rate_limit",
        resource_uid=scope_uid,
        evidence_source="services.email_send_rate_limiter",
        observed_at=expired_at,
    )
    store.events.extend([expired_allowed, durable_denial])
    session = _PostgresSession(store)
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: session)

    decision = await limiter_module.enforce_send_email_rate_limit(
        _context(), now=observed_at
    )

    assert decision.allowed is True
    assert expired_allowed not in store.events
    assert durable_denial in store.events
    assert sum(
        event.event_action == "email_send_rate_limit.allowed"
        and event.resource_uid == scope_uid
        for event in store.events
    ) == 1
    delete_query_index = next(
        index
        for index, query in enumerate(session.queries)
        if query.startswith("delete from security_audit_events")
    )
    count_query_index = next(
        index
        for index, query in enumerate(session.queries)
        if "count(" in query and "security_audit_events" in query
    )
    assert delete_query_index < count_query_index


@pytest.mark.asyncio
async def test_limiter_uses_owned_transaction_and_non_sensitive_audit_state(monkeypatch):
    store = _SharedAttemptStore()
    session = _PostgresSession(store)
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: session)
    decision = await limiter_module.enforce_send_email_rate_limit(
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
async def test_limiter_uses_database_clock_after_scope_lock(monkeypatch):
    store = _SharedAttemptStore()
    database_now = datetime.datetime(
        2026, 8, 19, 12, 34, 56, tzinfo=datetime.timezone.utc
    )
    session = _PostgresSession(store, database_now=database_now)
    monkeypatch.setattr(limiter_module, "AsyncSessionLocal", lambda: session)

    decision = await limiter_module.enforce_send_email_rate_limit(_context())

    assert decision.allowed is True
    lock_query_index = next(
        index
        for index, query in enumerate(session.queries)
        if "pg_advisory_xact_lock" in query
    )
    clock_query_index = next(
        index for index, query in enumerate(session.queries) if "clock_timestamp" in query
    )
    assert lock_query_index < clock_query_index
    audit = next(item for item in session.added if isinstance(item, SecurityAuditEvent))
    assert audit.observed_at == database_now


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
        with pytest.raises(limiter_module.EmailSendRateLimitUnavailable):
            await limiter_module.enforce_send_email_rate_limit(_context())
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
    scope_suffix = uuid.uuid4().hex
    context = _context(
        f"rate-limit-smoke-user-{scope_suffix}",
        f"rate-limit-smoke-org-{scope_suffix}",
    )
    scope_uid = (
        "email_send_scope:"
        f"{limiter_module.rate_limit_scope_hash(context.user_id, context.organization_id, context.workspace_id)}"
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

    try:
        await cleanup()
        try:
            first = await limiter_module.enforce_send_email_rate_limit(
                context, now=observed_at
            )
            second = await limiter_module.enforce_send_email_rate_limit(
                context, now=observed_at
            )
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
    finally:
        await engine.dispose()

    assert first.allowed is True
    assert second.allowed is False
    assert actions == [
        "email_send_rate_limit.allowed",
        "email_send_rate_limit.quota_exhausted",
    ]
