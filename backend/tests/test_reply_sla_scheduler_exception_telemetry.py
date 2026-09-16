"""Regression tests for Reply SLA exception telemetry confidentiality."""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from services import reply_sla_scheduler
from services.reply_sla_scheduler import ReplySlaScheduler, _sysrand


def _render_records(records: list[logging.LogRecord]) -> str:
    formatter = logging.Formatter("%(levelname)s %(name)s %(message)s")
    return "\n".join(formatter.format(record) for record in records)


@pytest.mark.asyncio
async def test_owner_escalation_failure_redacts_exception_and_owner_identifier(
    caplog, monkeypatch
):
    secret_owner = "alice+reply-sla-secret@example.com"
    secret_error = (
        "postgresql://operator:password@db.internal/naruon "
        "OPENAI_API_KEY=sk-reply-sla-secret"
    )

    class MockScalars:
        def all(self):
            return [
                SimpleNamespace(
                    user_id=secret_owner,
                    organization_id="org-acme",
                )
            ]

    class MockResult:
        def scalars(self):
            return MockScalars()

    class MockSession:
        async def execute(self, _statement):
            return MockResult()

    async def fail_owner_escalation(*_args, **_kwargs):
        raise RuntimeError(secret_error)

    monkeypatch.setattr(
        reply_sla_scheduler,
        "create_reply_sla_escalation_tasks",
        fail_owner_escalation,
    )

    with caplog.at_level(logging.ERROR, logger=reply_sla_scheduler.__name__):
        await ReplySlaScheduler()._sweep_configured_owners(MockSession())

    rendered = _render_records(caplog.records)
    assert "Overdue reply follow-up failed for configured owner." in rendered
    assert "exception_type=RuntimeError" in rendered
    assert "exception_fingerprint=" in rendered
    assert secret_error not in rendered
    assert "sk-reply-sla-secret" not in rendered
    assert "operator:password" not in rendered
    assert secret_owner not in rendered


@pytest.mark.asyncio
async def test_scheduler_loop_failure_redacts_exception_value_and_internal_path(
    caplog, monkeypatch
):
    secret_error = "provider token=sk-loop-secret path=/srv/naruon/private/tenant.db"
    scheduler = ReplySlaScheduler(interval_seconds=600)
    raised = asyncio.Event()

    monkeypatch.setattr(_sysrand, "uniform", lambda _minimum, _maximum: 0)

    async def fail_sync():
        raised.set()
        raise RuntimeError(secret_error)

    monkeypatch.setattr(scheduler, "_sync", fail_sync)

    with caplog.at_level(logging.ERROR, logger=reply_sla_scheduler.__name__):
        await scheduler.start()
        await asyncio.wait_for(raised.wait(), timeout=1)
        await asyncio.sleep(0)
        await scheduler.stop()

    rendered = _render_records(caplog.records)
    assert "Error in ReplySlaScheduler loop." in rendered
    assert "exception_type=RuntimeError" in rendered
    assert "exception_fingerprint=" in rendered
    assert secret_error not in rendered
    assert "sk-loop-secret" not in rendered
    assert "/srv/naruon/private/tenant.db" not in rendered
