"""Architecture contracts for the email-writing orchestration API boundary."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys


def test_email_writing_orchestrator_owns_a_dedicated_router_module() -> None:
    """Keep email-writing configuration isolated from legacy mailbox settings."""
    module = importlib.import_module("api.email_writing_orchestrator_config")
    tenant_config = importlib.import_module("api.tenant_config")

    route_paths = {route.path for route in module.router.routes}
    assert route_paths == {"/api/config/email-writing-orchestrator"}
    assert not hasattr(tenant_config, "EmailWritingOrchestratorConfigUpdate")
    assert not hasattr(tenant_config, "update_email_writing_orchestrator_config")


def test_orchestrator_port_import_does_not_materialize_runtime_settings() -> None:
    """Keep the domain-facing port import independent of application settings."""
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    backend_root = Path(__file__).resolve().parents[1]
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import services.email_writing_orchestrator_port; "
                "assert 'services.contextual_orchestrator_client' not in sys.modules; "
                "assert 'core.config' not in sys.modules"
            ),
        ],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
