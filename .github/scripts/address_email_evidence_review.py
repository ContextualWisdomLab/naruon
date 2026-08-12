"""Apply bounded CodeRabbit fixes for email-writing review evidence PR #1328."""

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    """Replace one exact reviewed anchor or fail closed on branch drift."""
    source = path.read_text(encoding="utf-8")
    occurrence_count = source.count(old)
    if occurrence_count != 1:
        raise SystemExit(
            f"{label} anchor mismatch: expected 1 occurrence, found {occurrence_count}"
        )
    path.write_text(source.replace(old, new), encoding="utf-8")


def update_evidence_serializer() -> None:
    """Remove tenant and sequential email identifiers from public evidence output."""
    path = Path("backend/db/email_writing_evidence.py")
    old = '''        return {
            "review_session_id": self.review_session_id,
            "owner_user_id": self.owner_user_id,
            "owner_organization_id": self.owner_organization_id,
            "source_email_id": self.source_email_id,
            "revision_algorithm": self.revision_algorithm,'''
    new = '''        return {
            "review_session_id": self.review_session_id,
            "revision_algorithm": self.revision_algorithm,'''
    replace_once(path, old, new, "privacy-minimized serializer")


def update_model_tests() -> None:
    """Guarantee engine cleanup and assert public serialization omits identifiers."""
    path = Path("backend/tests/test_email_writing_models.py")
    old_fixture = '''@pytest.fixture
def evidence_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql(
            "CREATE TABLE email_records (id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql("INSERT INTO email_records (id) VALUES (1)")
        for model_type in NEW_MODEL_TYPES:
            model_type.__table__.create(connection)
    with Session(engine) as session:
        yield session
    engine.dispose()
'''
    new_fixture = '''@pytest.fixture
def evidence_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.exec_driver_sql(
                "CREATE TABLE email_records (id INTEGER PRIMARY KEY)"
            )
            connection.exec_driver_sql("INSERT INTO email_records (id) VALUES (1)")
            for model_type in NEW_MODEL_TYPES:
                model_type.__table__.create(connection)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
'''
    replace_once(path, old_fixture, new_fixture, "model-test engine cleanup")

    old_assertions = '''    assert "review_session_id" in serialized
    assert "prompt_hash" in serialized
    assert "source_email_id" in serialized
    assert "candidate_hash" in serialized
    assert "feedback_action" in serialized
'''
    new_assertions = '''    assert "review_session_id" in serialized
    assert "prompt_hash" in serialized
    assert '"source_email_id"' not in serialized
    assert '"owner_user_id"' not in serialized
    assert '"owner_organization_id"' not in serialized
    assert "candidate_hash" in serialized
    assert "feedback_action" in serialized
'''
    replace_once(path, old_assertions, new_assertions, "privacy serialization assertions")


def update_migration_test_cleanup() -> None:
    """Dispose the migration-test engine even when setup or assertions fail."""
    path = Path("backend/tests/test_email_writing_migration.py")
    old = '''    engine = create_engine("sqlite:///:memory:")
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
'''
    new = '''    engine = create_engine("sqlite:///:memory:")
    try:
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
    finally:
        engine.dispose()
'''
    replace_once(path, old, new, "migration-test engine cleanup")


def update_evidence_workflow() -> None:
    """Run both test invocations under safety settings and reject bad output."""
    path = Path(".github/workflows/email-writing-evidence-tdd.yml")
    old = '''      - name: Run privacy-minimized model and migration tests
        run: |
          cd backend
          python -m pytest -q \\
            tests/test_email_writing_models.py \\
            tests/test_email_writing_migration.py
      - name: Verify migration statement and branch coverage
        run: |
          cd backend
          python -m coverage erase
          python -m coverage run --branch \\
            --include='alembic/versions/20260812_0001_add_email_writing_review_evidence.py' \\
            -m pytest -q tests/test_email_writing_migration.py
          python -m coverage report --show-missing --fail-under=100 \\
            alembic/versions/20260812_0001_add_email_writing_review_evidence.py
'''
    new = '''      - name: Run privacy-minimized model and migration tests
        env:
          PYTHONWARNINGS: error
          DISABLE_BACKGROUND_WORKERS: "1"
        run: |
          set -euo pipefail
          cd backend
          output_file="$(mktemp)"
          trap 'rm -f "$output_file"' EXIT
          set +e
          python -m pytest -q \\
            tests/test_email_writing_models.py \\
            tests/test_email_writing_migration.py 2>&1 | tee "$output_file"
          test_status=${PIPESTATUS[0]}
          set -e
          if grep -Eiq '(^|[^[:alnum:]_])(Timeout|Fatal|Warn|Denied)([^[:alnum:]_]|$)' "$output_file"; then
            echo "::error::Backend tests emitted prohibited stability output."
            exit 1
          fi
          exit "$test_status"
      - name: Verify migration statement and branch coverage
        env:
          PYTHONWARNINGS: error
          DISABLE_BACKGROUND_WORKERS: "1"
        run: |
          set -euo pipefail
          cd backend
          output_file="$(mktemp)"
          trap 'rm -f "$output_file"' EXIT
          python -m coverage erase
          set +e
          python -m coverage run --branch \\
            --include='alembic/versions/20260812_0001_add_email_writing_review_evidence.py' \\
            -m pytest -q tests/test_email_writing_migration.py 2>&1 | tee "$output_file"
          test_status=${PIPESTATUS[0]}
          set -e
          if grep -Eiq '(^|[^[:alnum:]_])(Timeout|Fatal|Warn|Denied)([^[:alnum:]_]|$)' "$output_file"; then
            echo "::error::Coverage tests emitted prohibited stability output."
            exit 1
          fi
          if [[ "$test_status" -ne 0 ]]; then
            exit "$test_status"
          fi
          python -m coverage report --show-missing --fail-under=100 \\
            alembic/versions/20260812_0001_add_email_writing_review_evidence.py
'''
    replace_once(path, old, new, "evidence workflow safety settings")


def main() -> None:
    """Apply all currently valid review fixes in one bounded mutation."""
    update_evidence_serializer()
    update_model_tests()
    update_migration_test_cleanup()
    update_evidence_workflow()


if __name__ == "__main__":
    main()
