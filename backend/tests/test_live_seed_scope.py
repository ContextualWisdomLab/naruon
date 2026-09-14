"""Owner-scope regressions for the live Docker E2E seed helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SEED_MODULE_PATH = BACKEND_ROOT / "tests" / "live" / "seed_live_data.py"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("live_seed_data", SEED_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_live_seed_email_cleanup_is_workspace_owner_scoped():
    """Fixture cleanup must never delete another workspace's reused Message-ID."""
    module = _load_seed_module()

    class CapturingSession:
        def __init__(self) -> None:
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return None

    session = CapturingSession()
    await module._cleanup_existing_data(session)

    email_delete = session.statements[-1]
    compiled = email_delete.compile()
    query_text = str(compiled)
    parameter_values = list(compiled.params.values())
    expanding_parameter_values = [
        value
        for value in parameter_values
        if isinstance(value, (list, tuple, set, frozenset))
    ]

    assert "email_records.user_id" in query_text
    assert "email_records.organization_id" in query_text
    assert "email_records.workspace_id" in query_text
    assert "email_records.message_id" in query_text
    assert module.LIVE_E2E_USER_ID in parameter_values
    assert module.LIVE_E2E_ORGANIZATION_ID in parameter_values
    assert module.LIVE_E2E_WORKSPACE_ID in parameter_values
    assert any(list(value) == module.MESSAGE_IDS for value in expanding_parameter_values)
