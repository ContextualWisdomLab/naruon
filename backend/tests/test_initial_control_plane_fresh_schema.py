import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REVISION_PATH = BACKEND_ROOT / "alembic" / "versions" / "0001_initial_control_plane.py"


def _load_revision_module():
    spec = importlib.util.spec_from_file_location("initial_control_plane", REVISION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ConnectionRecorder:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, statement) -> None:
        self.executed.append(str(statement))


def _exercise_upgrade(monkeypatch, *, legacy_emails_present: bool) -> list[str]:
    revision = _load_revision_module()
    connection = _ConnectionRecorder()

    class _Inspector:
        @staticmethod
        def has_table(table_name: str) -> bool:
            assert table_name == "emails"
            return legacy_emails_present

    monkeypatch.setattr(revision.op, "get_bind", lambda: connection)
    monkeypatch.setattr(revision, "inspect", lambda _: _Inspector())
    monkeypatch.setattr(revision.Base.metadata, "create_all", lambda _: None)
    monkeypatch.setattr(
        revision,
        "schema_backfill_sql",
        lambda: [
            text(
                "CREATE INDEX IF NOT EXISTS ix_emails_owner_date "
                "ON emails (user_id, organization_id, date)"
            ),
            text(
                "CREATE INDEX IF NOT EXISTS ix_email_records_owner_date "
                "ON email_records (user_id, organization_id, date)"
            ),
        ],
    )

    revision.upgrade()
    return connection.executed


def test_fresh_schema_skips_retired_emails_index(monkeypatch):
    executed = _exercise_upgrade(monkeypatch, legacy_emails_present=False)

    assert not any("ix_emails_owner_date" in statement for statement in executed)
    assert any("ix_email_records_owner_date" in statement for statement in executed)


def test_legacy_schema_preserves_emails_compatibility_index(monkeypatch):
    executed = _exercise_upgrade(monkeypatch, legacy_emails_present=True)

    assert any("ix_emails_owner_date" in statement for statement in executed)
    assert any("ix_email_records_owner_date" in statement for statement in executed)


@pytest.mark.parametrize(
    ("table_name", "preexisting_read"),
    [("email_records", True), ("email_records", False), ("emails", False)],
)
def test_read_state_upgrade_preserves_existing_values(table_name, preexisting_read):
    path = BACKEND_ROOT / "alembic" / "versions" / "0011_email_read_state.py"
    spec = importlib.util.spec_from_file_location("email_read_state_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            read_column = ", is_read BOOLEAN NOT NULL" if preexisting_read else ""
            connection.exec_driver_sql(
                f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY{read_column})"
            )
            connection.exec_driver_sql(
                f"INSERT INTO {table_name} VALUES (1{', 0' if preexisting_read else ''})"
            )
            revision.op = Operations(MigrationContext.configure(connection))
            revision.upgrade()
            revision.upgrade()
            assert connection.exec_driver_sql(
                f"SELECT is_read FROM {table_name} WHERE id = 1"
            ).scalar_one() == (0 if preexisting_read else 1)
            revision.downgrade()
            assert connection.exec_driver_sql(
                f"SELECT is_read FROM {table_name} WHERE id = 1"
            ).scalar_one() == (0 if preexisting_read else 1)
    finally:
        engine.dispose()
