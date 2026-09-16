import logging

import pytest
from sqlalchemy.exc import SQLAlchemyError

from api import runner_ws


class _SecretFailingRunnerConnection:
    def __init__(self, secret_detail: str):
        self.secret_detail = secret_detail

    async def send_text(self, _text: str) -> None:
        raise RuntimeError(self.secret_detail)


@pytest.mark.asyncio
async def test_runner_signal_persistence_failure_redacts_database_exception_details(
    monkeypatch,
    caplog,
):
    secret_detail = (
        "postgresql://alice:super-secret@db.internal/naruon "
        "token=sk-runner-private"
    )

    async def fail_record_connector_signal_event(**_kwargs):
        raise SQLAlchemyError(secret_detail)

    monkeypatch.setattr(
        runner_ws,
        "record_connector_signal_event",
        fail_record_connector_signal_event,
    )
    caplog.set_level(logging.DEBUG, logger=runner_ws.__name__)

    await runner_ws._record_connector_signal_event_safely(
        organization_id="org-acme",
        workspace_id="workspace-org-acme",
        signal_key="connector_heartbeat",
        state_code="heartbeat",
        detail_text="outbound runner heartbeat received",
    )

    rendered_log = caplog.text
    assert "Runner signal event persistence skipped" in rendered_log
    assert "exception_type=SQLAlchemyError" in rendered_log
    assert "exception_fingerprint=" in rendered_log
    assert secret_detail not in rendered_log
    assert "super-secret" not in rendered_log
    assert "sk-runner-private" not in rendered_log
    assert "Traceback (most recent call last)" not in rendered_log


@pytest.mark.asyncio
async def test_runner_command_dispatch_failure_redacts_transport_exception_details(
    monkeypatch,
    caplog,
):
    secret_detail = "/srv/naruon/private/socket token=sk-runner-dispatch-private"
    connection_key = "org-acme:runner"
    runner_ws.manager.active_connections[connection_key] = _SecretFailingRunnerConnection(
        secret_detail
    )
    runner_ws.manager.connection_records[connection_key] = runner_ws.RunnerConnectionRecord(
        organization_id="org-acme",
        workspace_id="workspace-org-acme",
        connected_at="2026-09-17T00:00:00Z",
    )

    async def noop_record_connector_command_event_safely(**_kwargs):
        return None

    monkeypatch.setattr(
        runner_ws,
        "_record_connector_command_event_safely",
        noop_record_connector_command_event_safely,
    )
    caplog.set_level(logging.ERROR, logger=runner_ws.__name__)

    response = await runner_ws.manager.dispatch_command(
        organization_id="org-acme",
        workspace_id="workspace-org-acme",
        command={"action": "writeback"},
        schedule_retry=False,
    )

    assert response["status"] == "error"
    assert response["error_code"] == "runner_dispatch_failed"
    rendered_log = caplog.text
    assert "Runner command dispatch failed." in rendered_log
    assert "exception_type=RuntimeError" in rendered_log
    assert "exception_fingerprint=" in rendered_log
    assert secret_detail not in rendered_log
    assert "sk-runner-dispatch-private" not in rendered_log
    assert "Traceback (most recent call last)" not in rendered_log
