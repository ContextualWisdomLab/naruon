import logging

import pytest
from sqlalchemy.exc import SQLAlchemyError

from api import runner_ws


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
