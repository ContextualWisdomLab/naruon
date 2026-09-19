from pathlib import Path

from scripts.bootstrap_db import schema_backfill_sql


def _schema_statements() -> list[str]:
    return [str(statement).lower() for statement in schema_backfill_sql()]


def _uid_backfill_statements() -> list[str]:
    prefixes = (
        "update prompt_templates set prompt_uid",
        "update webdav_accounts set source_uid",
        "update project_folders set folder_uid",
    )
    return [
        statement
        for statement in _schema_statements()
        if any(prefix in statement for prefix in prefixes)
    ]


def test_bootstrap_opaque_uid_backfills_use_uuid_v4_entropy():
    statements = _uid_backfill_statements()

    assert len(statements) == 3
    assert all("gen_random_uuid()::text" in statement for statement in statements)
    assert all("random()::text" not in statement for statement in statements)


def test_prompt_scope_migration_uses_uuid_v4_entropy_for_legacy_uid_backfill():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0003_prompt_template_scope.py"
    )
    migration_source = migration_path.read_text(encoding="utf-8").lower()

    assert "set prompt_uid = 'prompt_'" in migration_source
    assert "gen_random_uuid()::text" in migration_source
    assert "random()::text" not in migration_source
