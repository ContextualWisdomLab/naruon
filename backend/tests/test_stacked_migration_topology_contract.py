"""Stacked Alembic topology contracts for #1503 -> #1486 reconciliation."""

from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revision_text(filename: str) -> str:
    return (VERSIONS_DIR / filename).read_text(encoding="utf-8")


def test_calendar_conflict_line_descends_from_canonical_workspace_repair() -> None:
    """Keep #1486's migrations linear after #1503's append-only repair.

    Numeric filename prefixes are historical labels, not graph authority. The
    immutable revision identifiers stay unchanged; only the first descendant's
    parent moves to the canonical prerequisite head so a stacked merge cannot
    create parallel Alembic heads.
    """
    calendar_conflict = _revision_text("0018_calendar_conflict_judgments.py")
    attachment_uid = _revision_text("0019_attachment_uid.py")
    email_workspace = _revision_text("0020_email_workspace_scope.py")
    calendar_rationale = _revision_text("0021_calendar_correction_rationale.py")
    noema_gateway = _revision_text("0022_noema_orchestrator_gateway.py")

    assert 'down_revision = "0019_email_read_state_repair"' in calendar_conflict
    assert 'down_revision = "0018_calendar_conflict_judgments"' in attachment_uid
    assert 'down_revision = "0019_attachment_uid"' in email_workspace
    assert 'down_revision = "0020_email_workspace_scope"' in calendar_rationale
    assert 'down_revision = "0021_calendar_rationale"' in noema_gateway
