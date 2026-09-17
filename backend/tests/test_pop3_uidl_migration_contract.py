from pathlib import Path

from db.pop3_collection_models import Pop3ObservedMessage


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0019_pop3_observed_uidl.py"
)


def test_pop3_uidl_model_is_owner_scoped_and_bounded():
    table = Pop3ObservedMessage.__table__

    assert table.name == "pop3_observed_messages"
    assert table.c.tenant_config_id.nullable is False
    assert table.c.provider_uidl.nullable is False
    assert table.c.provider_uidl.type.length == 70
    assert any(
        constraint.name == "uq_pop3_observed_messages_account_uidl"
        for constraint in table.constraints
    )


def test_pop3_uidl_migration_succeeds_canonical_provenance_revision():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "0019_pop3_observed_uidl"' in source
    assert 'down_revision = "0018_email_date_provenance"' in source
    assert 'sa.ForeignKey("tenant_configs.id", ondelete="CASCADE")' in source
    assert 'sa.String(length=70)' in source
    assert '"uq_pop3_observed_messages_account_uidl"' in source
