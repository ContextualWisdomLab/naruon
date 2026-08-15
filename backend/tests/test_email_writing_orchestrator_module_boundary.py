"""Architecture contracts for the email-writing orchestration API boundary."""

from __future__ import annotations

import importlib


def test_email_writing_orchestrator_owns_a_dedicated_router_module() -> None:
    """Keep email-writing configuration isolated from legacy mailbox settings."""
    module = importlib.import_module("api.email_writing_orchestrator_config")
    tenant_config = importlib.import_module("api.tenant_config")

    route_paths = {route.path for route in module.router.routes}
    assert route_paths == {"/api/config/email-writing-orchestrator"}
    assert not hasattr(tenant_config, "EmailWritingOrchestratorConfigUpdate")
    assert not hasattr(tenant_config, "update_email_writing_orchestrator_config")
