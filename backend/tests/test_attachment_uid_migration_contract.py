import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _load_revision_module():
    path = BACKEND_ROOT / "alembic" / "versions" / "0019_attachment_uid.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_attachment_uid_upgrade_offline_uses_set_based_update(monkeypatch):
    module = _load_revision_module()
    operations = []

    monkeypatch.setattr(module.context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(
        module.op,
        "get_bind",
        lambda: pytest.fail("offline migration must not request a live connection"),
    )
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _connection: pytest.fail("offline migration must not inspect a live database"),
    )
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *args, **kwargs: operations.append(("add_column", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "execute",
        lambda statement: operations.append(("execute", statement, {})),
    )
    monkeypatch.setattr(
        module.op,
        "alter_column",
        lambda *args, **kwargs: operations.append(("alter_column", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "create_index",
        lambda *args, **kwargs: operations.append(("create_index", args, kwargs)),
    )

    module.upgrade()

    assert [operation[0] for operation in operations] == [
        "add_column",
        "execute",
        "alter_column",
        "create_index",
    ]
    update_statement = operations[1][1]
    assert isinstance(update_statement, sa.sql.dml.Update)
    compiled = str(
        update_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "UPDATE email_attachments SET attachment_uid=concat(" in compiled
    assert "gen_random_uuid()" in compiled
    assert "WHERE email_attachments.attachment_uid IS NULL" in compiled


def test_attachment_uid_downgrade_offline_emits_linear_operations(monkeypatch):
    module = _load_revision_module()
    operations = []

    monkeypatch.setattr(module.context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(
        module.op,
        "get_bind",
        lambda: pytest.fail("offline migration must not request a live connection"),
    )
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _connection: pytest.fail("offline migration must not inspect a live database"),
    )
    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda *args, **kwargs: pytest.fail(
            "offline downgrade cannot infer constraint-backed bootstrap shape"
        ),
    )
    monkeypatch.setattr(
        module.op,
        "drop_index",
        lambda *args, **kwargs: operations.append(("drop_index", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "drop_column",
        lambda *args, **kwargs: operations.append(("drop_column", args, kwargs)),
    )

    module.downgrade()

    assert [operation[0] for operation in operations] == ["drop_index", "drop_column"]
    assert operations[0][2]["if_exists"] is True


def test_attachment_uid_backfill_has_no_python_row_loop():
    source = (
        BACKEND_ROOT / "alembic" / "versions" / "0019_attachment_uid.py"
    ).read_text()

    assert ".fetchall()" not in source
    assert "uuid.uuid4" not in source
