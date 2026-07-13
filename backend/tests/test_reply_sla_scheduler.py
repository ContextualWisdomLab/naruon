import asyncio

import pytest

from db.models import TenantConfig
from services.reply_sla_scheduler import ReplySlaScheduler


@pytest.mark.asyncio
async def test_reply_sla_scheduler_escalates_configured_mailbox_owners(monkeypatch):
    calls: list[dict[str, object]] = []

    class MockScalars:
        def all(self):
            return [
                TenantConfig(
                    user_id="alice",
                    organization_id="org-acme",
                    smtp_username="alice@example.com",
                ),
                TenantConfig(
                    user_id="bob",
                    organization_id="org-beta",
                    imap_username="bob@example.com",
                ),
            ]

    class MockResult:
        def scalars(self):
            return MockScalars()

    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, stmt):
            self.statement = stmt
            return MockResult()

    session = MockSession()

    async def fake_create_reply_sla_escalation_tasks(
        db, *, user_id, organization_id, overdue_hours, limit, tenant_config
    ):
        calls.append(
            {
                "db": db,
                "user_id": user_id,
                "organization_id": organization_id,
                "overdue_hours": overdue_hours,
                "limit": limit,
                "tenant_config": tenant_config,
            }
        )

    monkeypatch.setattr(
        "services.reply_sla_scheduler.AsyncSessionLocal",
        lambda: session,
    )
    monkeypatch.setattr(
        "services.reply_sla_scheduler.create_reply_sla_escalation_tasks",
        fake_create_reply_sla_escalation_tasks,
    )

    scheduler = ReplySlaScheduler(overdue_hours=24, limit=7)

    await scheduler._sync()

    assert calls == [
        {
            "db": session,
            "user_id": "alice",
            "organization_id": "org-acme",
            "overdue_hours": 24,
            "limit": 7,
            "tenant_config": calls[0]["tenant_config"],
        },
        {
            "db": session,
            "user_id": "bob",
            "organization_id": "org-beta",
            "overdue_hours": 24,
            "limit": 7,
            "tenant_config": calls[1]["tenant_config"],
        },
    ]
    assert calls[0]["tenant_config"].smtp_username == "alice@example.com"
    assert calls[1]["tenant_config"].imap_username == "bob@example.com"


@pytest.mark.asyncio
async def test_reply_sla_scheduler_continues_after_owner_escalation_failure(
    monkeypatch,
):
    calls: list[str] = []

    class MockScalars:
        def all(self):
            return [
                TenantConfig(user_id="alice", organization_id="org-acme"),
                TenantConfig(user_id="bob", organization_id="org-beta"),
            ]

    class MockResult:
        def scalars(self):
            return MockScalars()

    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, stmt):
            return MockResult()

    async def fake_create_reply_sla_escalation_tasks(
        db, *, user_id, organization_id, overdue_hours, limit, tenant_config
    ):
        calls.append(user_id)
        if user_id == "alice":
            raise RuntimeError("tenant escalation failed")

    monkeypatch.setattr(
        "services.reply_sla_scheduler.AsyncSessionLocal",
        lambda: MockSession(),
    )
    monkeypatch.setattr(
        "services.reply_sla_scheduler.create_reply_sla_escalation_tasks",
        fake_create_reply_sla_escalation_tasks,
    )

    await ReplySlaScheduler()._sync()

    assert calls == ["alice", "bob"]


@pytest.mark.asyncio
async def test_reply_sla_scheduler_start_stop_cancels_loop(monkeypatch):
    scheduler = ReplySlaScheduler(interval_seconds=60)
    started = asyncio.Event()

    async def fake_run_loop():
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(scheduler, "_run_loop", fake_run_loop)

    await scheduler.start()
    await started.wait()
    assert scheduler._is_running is True
    assert scheduler._task is not None

    await scheduler.stop()

    assert scheduler._is_running is False
