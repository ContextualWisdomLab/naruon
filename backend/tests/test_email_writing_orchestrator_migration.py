"""Migration contract for email-writing orchestration configuration."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "20260813_0001_add_email_writing_orchestrator_config.py"
)


def test_orchestrator_configuration_has_an_alembic_revision() -> None:
    """A production deployment can create the configuration table."""
    assert MIGRATION_PATH.is_file()


def test_alembic_environment_registers_orchestrator_configuration() -> None:
    """Autogenerate includes the modular configuration model metadata."""
    environment_source = (BACKEND_ROOT / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "EmailWritingOrchestratorConfig" in environment_source
