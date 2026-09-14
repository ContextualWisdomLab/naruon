"""Offline-mode contract tests for the Noema gateway Alembic revision."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0022_noema_orchestrator_gateway.py"
)


def _load_migration():
    """Load the revision module without depending on package import side effects."""
    spec = importlib.util.spec_from_file_location(
        "offline_contract_0022_noema_orchestrator_gateway",
        _MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("direction", "operation_name", "expected_columns"),
    (
        (
            "upgrade",
            "add_column",
            ["noema_orchestrator_base_url", "noema_orchestrator_token"],
        ),
        (
            "downgrade",
            "drop_column",
            ["noema_orchestrator_token", "noema_orchestrator_base_url"],
        ),
    ),
)
def test_noema_gateway_migration_emits_linear_offline_operations_without_introspection(
    monkeypatch: pytest.MonkeyPatch,
    direction: str,
    operation_name: str,
    expected_columns: list[str],
) -> None:
    """Offline SQL generation must not require a live bind or catalog inspection."""
    migration = _load_migration()
    monkeypatch.setattr(
        migration,
        "context",
        SimpleNamespace(is_offline_mode=lambda: True),
        raising=False,
    )
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: pytest.fail("offline migration requested a live Alembic bind"),
    )
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda *_args, **_kwargs: pytest.fail(
            "offline migration attempted live schema introspection"
        ),
    )

    emitted_columns: list[str] = []
    if operation_name == "add_column":
        monkeypatch.setattr(
            migration.op,
            "add_column",
            lambda table_name, column, **_kwargs: emitted_columns.append(column.name),
        )
    else:
        monkeypatch.setattr(
            migration.op,
            "drop_column",
            lambda table_name, column_name, **_kwargs: emitted_columns.append(column_name),
        )

    getattr(migration, direction)()

    assert emitted_columns == expected_columns
