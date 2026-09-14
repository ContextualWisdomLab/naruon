"""Regression contract for the historical document organization-scope revision."""

import importlib.util
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REVISION_PATH = BACKEND_ROOT / "alembic" / "versions" / "0016_document_org_scope.py"


def _load_revision_module():
    spec = importlib.util.spec_from_file_location("document_org_scope_revision", REVISION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_is_noop_when_historical_database_has_no_document_table(monkeypatch):
    module = _load_revision_module()
    operations = []

    class Inspector:
        @staticmethod
        def has_table(table_name):
            assert table_name == "workspace_documents"
            return False

    monkeypatch.setattr(module.op, "get_bind", lambda: object())
    monkeypatch.setattr(module.sa, "inspect", lambda _connection: Inspector())
    monkeypatch.setattr(module.op, "add_column", lambda *args, **kwargs: operations.append((args, kwargs)))
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: operations.append((args, kwargs)))

    module.upgrade()

    assert operations == []


def test_downgrade_never_removes_later_workspace_document_assignments(monkeypatch):
    module = _load_revision_module()
    operations = []

    monkeypatch.setattr(module.op, "drop_index", lambda *args, **kwargs: operations.append((args, kwargs)))
    monkeypatch.setattr(module.op, "drop_column", lambda *args, **kwargs: operations.append((args, kwargs)))

    module.downgrade()

    assert operations == []
