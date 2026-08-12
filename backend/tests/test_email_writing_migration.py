"""Executable migration contracts for email-writing review evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from db.email_writing_evidence import (
    DiagnosticFeedbackEvent,
    EmailReviewSession,
    WritingDiagnosticRecord,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "20260812_0001_add_email_writing_review_evidence.py"
)
NEW_TABLE_NAMES = (
    "email_review_session",
    "writing_diagnostic_record",
    "diagnostic_feedback_event",
)
FORBIDDEN_PLAINTEXT_NAMES = (
    "source_body",
    "draft_text",
    "replacement_text",
    "explanation_text",
    "prompt_text",
    "raw_output",
    "provider_token",
    "orchestration_trace",
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "email_writing_review_evidence_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_environment_registers_review_evidence_metadata() -> None:
    """Autogenerate sees the modular evidence models without editing the legacy file."""
    environment_source = (BACKEND_ROOT / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "email_writing_evidence" in environment_source
    assert (
        "target_metadata = EmailReviewSession.__table__.metadata"
        in environment_source
    )


def test_migration_revision_and_metadata_match_orm_contract() -> None:
    """The revision graph and table definitions remain synchronized with ORM code."""
    module = _load_migration()
    assert module.revision == "20260812_email_writing_evidence"
    assert module.down_revision == "0017_merge_newsdom_carddav_heads"

    migration_metadata = module._review_evidence_metadata()
    orm_tables = {
        EmailReviewSession.__table__.name: EmailReviewSession.__table__,
        WritingDiagnosticRecord.__table__.name: WritingDiagnosticRecord.__table__,
        DiagnosticFeedbackEvent.__table__.name: DiagnosticFeedbackEvent.__table__,
    }
    for table_name in NEW_TABLE_NAMES:
        assert set(migration_metadata.tables[table_name].columns.keys()) == set(
            orm_tables[table_name].columns.keys()
        )
        assert {
            constraint.name
            for constraint in migration_metadata.tables[table_name].constraints
        } == {constraint.name for constraint in orm_tables[table_name].constraints}
        assert {
            index.name for index in migration_metadata.tables[table_name].indexes
        } == {index.name for index in orm_tables[table_name].indexes}


def test_sqlite_upgrade_downgrade_is_idempotent_and_preserves_unrelated_objects(
    monkeypatch,
) -> None:
    """SQLite receives all objects, and downgrade removes only this revision's DDL."""
    module = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql(
            "CREATE TABLE email_records (id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE unrelated_audit_record "
            "(audit_record_id INTEGER PRIMARY KEY)"
        )
        monkeypatch.setattr(
            module,
            "op",
            SimpleNamespace(get_bind=lambda: connection),
        )

        module.upgrade()
        module.upgrade()
        database_inspector = inspect(connection)
        assert set(NEW_TABLE_NAMES).issubset(database_inspector.get_table_names())
        assert "unrelated_audit_record" in database_inspector.get_table_names()
        assert "email_records" in database_inspector.get_table_names()

        assert {
            index["name"]
            for index in database_inspector.get_indexes("email_review_session")
        } >= {
            "ix_email_review_session_owner_scope",
            "ix_email_review_session_expiry_status",
            "ix_email_review_session_source_email",
        }
        assert {
            constraint["name"]
            for constraint in database_inspector.get_check_constraints(
                "writing_diagnostic_record"
            )
        } >= {
            "ck_writing_diagnostic_record_selector_order",
            "ck_writing_diagnostic_record_judge_score",
            "ck_writing_diagnostic_record_admission_status",
        }

        module.downgrade()
        module.downgrade()
        remaining_tables = set(inspect(connection).get_table_names())
        assert remaining_tables.isdisjoint(NEW_TABLE_NAMES)
        assert "unrelated_audit_record" in remaining_tables
        assert "email_records" in remaining_tables
    engine.dispose()


def test_postgresql_ddl_compiles_with_named_constraints_and_indexes() -> None:
    """The same metadata emits PostgreSQL-compatible named DDL without raw content."""
    module = _load_migration()
    metadata = module._review_evidence_metadata()
    rendered_statements: list[str] = []
    for table_name in NEW_TABLE_NAMES:
        table = metadata.tables[table_name]
        rendered_statements.append(
            str(CreateTable(table).compile(dialect=postgresql.dialect()))
        )
        rendered_statements.extend(
            str(CreateIndex(index).compile(dialect=postgresql.dialect()))
            for index in table.indexes
        )

    rendered_ddl = "\n".join(rendered_statements).lower()
    for table_name in NEW_TABLE_NAMES:
        assert table_name in rendered_ddl
    for required_fragment in (
        "foreign key",
        "on delete cascade",
        "check",
        "unique",
        "criterion_categories_json json",
        "ix_email_review_session_expiry_status",
        "uq_writing_diagnostic_record_session_identifier",
        "uq_diagnostic_feedback_event_owner_idempotency",
    ):
        assert required_fragment in rendered_ddl
    for forbidden_name in FORBIDDEN_PLAINTEXT_NAMES:
        assert forbidden_name not in rendered_ddl


def test_migration_source_contains_no_plaintext_evidence_fields() -> None:
    """Static review cannot regress into storing mail, draft, or provider plaintext."""
    source = MIGRATION_PATH.read_text(encoding="utf-8").lower()
    for forbidden_name in FORBIDDEN_PLAINTEXT_NAMES:
        assert forbidden_name not in source
    assert "source_email_id" in source
    assert "candidate_hash" in source
    assert "replacement_hash" in source
    assert "explanation_hash" in source
    assert "evidence_expires_at" in source
