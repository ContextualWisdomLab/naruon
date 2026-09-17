from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_email_date_provenance_migration_contract() -> None:
    revision_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0018_email_date_provenance.py"
    )
    revision_text = revision_path.read_text()

    assert 'revision = "0018_email_date_provenance"' in revision_text
    assert 'down_revision = "0017_merge_newsdom_carddav_heads"' in revision_text
    assert '_EMAIL_TABLE = "email_records"' in revision_text
    assert '_PROVENANCE_COLUMN = "date_provenance"' in revision_text
    assert "nullable=False" in revision_text
    assert 'server_default="unknown"' in revision_text

    assert 'op.add_column(' in revision_text
    assert 'op.drop_column(_EMAIL_TABLE, _PROVENANCE_COLUMN)' in revision_text


def test_canonical_email_provenance_does_not_fork_parallel_evidence_columns() -> None:
    revision_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0018_email_date_provenance.py"
    )
    revision_text = revision_path.read_text()

    assert "date_evidence" not in revision_text
    assert "message_id_evidence" not in revision_text
