import importlib.util
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REVISION_PATH = BACKEND_ROOT / "alembic" / "versions" / "0020_email_workspace_scope.py"


def _load_revision_module():
    spec = importlib.util.spec_from_file_location(REVISION_PATH.stem, REVISION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _compiled_sql(statement) -> str:
    return " ".join(
        str(statement.compile(compile_kwargs={"literal_binds": True})).split()
    ).lower()


def test_0020_workspace_backfill_is_operator_authoritative_not_org_derived():
    revision_text = REVISION_PATH.read_text()

    assert 'sa.func.concat("workspace-", emails.c.organization_id)' not in revision_text
    assert "email_workspace_mapping_json" in revision_text
    assert "email_workspace_fallback" in revision_text


def test_0020_blank_workspace_is_unresolved_for_backfill_and_validation():
    module = _load_revision_module()
    emitted = []

    module._apply_workspace_backfill(
        emitted.append,
        {17: "workspace-mapped"},
        "workspace-fallback",
    )

    assert len(emitted) == 2
    for statement in emitted:
        sql = _compiled_sql(statement)
        assert "workspace_id is null" in sql
        assert "trim(email_records.workspace_id) = ''" in sql

    emails = module._email_table_stub()
    unresolved_sql = _compiled_sql(
        module.sa.select(module.sa.func.count())
        .select_from(emails)
        .where(module._workspace_is_unresolved(emails))
    )
    assert "workspace_id is null" in unresolved_sql
    assert "trim(email_records.workspace_id) = ''" in unresolved_sql


def test_0020_offline_upgrade_uses_operator_fallback_without_live_inspection(monkeypatch):
    module = _load_revision_module()
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(module.context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(
        module.context,
        "get_x_argument",
        lambda *, as_dictionary: {
            "email_workspace_fallback": "workspace-operator-validated"
        },
    )
    monkeypatch.setattr(
        module.op,
        "get_bind",
        lambda: pytest.fail("offline migration must not request a live bind"),
    )
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *args, **kwargs: events.append(("add_column", (args, kwargs))),
    )
    monkeypatch.setattr(
        module.op,
        "execute",
        lambda statement: events.append(("execute", statement.compile().params)),
    )
    monkeypatch.setattr(
        module.op,
        "alter_column",
        lambda *args, **kwargs: events.append(("alter_column", (args, kwargs))),
    )
    monkeypatch.setattr(
        module.op,
        "create_index",
        lambda *args, **kwargs: events.append(("create_index", (args, kwargs))),
    )
    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda *args, **kwargs: events.append(("drop_constraint", (args, kwargs))),
    )
    monkeypatch.setattr(
        module.op,
        "drop_index",
        lambda *args, **kwargs: events.append(("drop_index", (args, kwargs))),
    )
    monkeypatch.setattr(
        module.op,
        "create_unique_constraint",
        lambda *args, **kwargs: events.append(
            ("create_unique_constraint", (args, kwargs))
        ),
    )

    module.upgrade()

    event_names = [name for name, _payload in events]
    assert event_names.index("execute") < event_names.index("alter_column")
    execute_params = next(payload for name, payload in events if name == "execute")
    assert "workspace-operator-validated" in execute_params.values()
    assert "create_unique_constraint" in event_names


def test_0020_offline_downgrade_is_fail_closed_without_owner_identity_ack(monkeypatch):
    module = _load_revision_module()

    monkeypatch.setattr(module.context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(module.context, "get_x_argument", lambda *, as_dictionary: {})
    monkeypatch.setattr(
        module.op,
        "get_bind",
        lambda: pytest.fail("offline migration must not request a live bind"),
    )

    with pytest.raises(RuntimeError, match="email_workspace_downgrade_owner_identity_verified"):
        module.downgrade()
