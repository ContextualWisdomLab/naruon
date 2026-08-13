"""Add the owner-scoped email-writing orchestration table."""

from __future__ import annotations

from alembic import op

from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig

revision = "20260813_email_orchestrator"
down_revision = "20260812_email_writing_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the configuration table and its indexes."""
    EmailWritingOrchestratorConfig.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Drop only the configuration table introduced by this revision."""
    EmailWritingOrchestratorConfig.__table__.drop(op.get_bind(), checkfirst=True)
