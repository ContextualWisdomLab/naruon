import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize(
    ("table", "already_present"),
    [("email_records", False), ("email_records", True), ("emails", False)],
)
def test_read_state_upgrade_preserves_existing_rows(table, already_present):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0011_email_read_state.py"
    )
    spec = importlib.util.spec_from_file_location("email_read_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        columns = ", is_read BOOLEAN NOT NULL DEFAULT true" if already_present else ""
        connection.execute(
            sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY{columns})")
        )
        connection.execute(sa.text(f"INSERT INTO {table} (id) VALUES (1)"))
        if already_present:
            connection.execute(sa.text(f"UPDATE {table} SET is_read = false"))
        expected = 0 if already_present else 1
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
            assert (
                connection.execute(sa.text(f"SELECT is_read FROM {table}")).scalar_one()
                == expected
            )
            module.downgrade()
        assert "is_read" in {
            column["name"] for column in sa.inspect(connection).get_columns(table)
        }
        assert (
            connection.execute(sa.text(f"SELECT is_read FROM {table}")).scalar_one()
            == expected
        )
    engine.dispose()
