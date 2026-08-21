"""Email-model reconciliation guards (naruon#975, P0).

`email_records` is the single email source of truth; account/provider
configuration lives in `tenant_configs` (/api/accounts),
`caldav_accounts`, and `webdav_accounts`. The abandoned parallel
account-centric email model (user_accounts / provider_accounts /
email_raws / email_messages / email_instances / email_threads /
email_thread_edges) was removed after verification that it had zero
importers, no alembic migration, and no bootstrap coverage. These
guards keep it from silently returning; the P2 multi-account identity
binding builds on the KG (first-class identity entities), not on a
parallel email store — see
docs/engineering/email-model-reconciliation.md.
"""

import db.models as db_models

_RETIRED_TABLE_NAMES = (
    "user_accounts",
    "provider_accounts",
    "email_raws",
    "email_messages",
    "email_instances",
    "email_threads",
    "email_thread_edges",
)

_RETIRED_MODEL_CLASS_NAMES = (
    "User",
    "Account",
    "EmailRaw",
    "EmailMessage",
    "EmailInstance",
    "EmailThread",
    "EmailThreadEdge",
)


def test_retired_parallel_email_tables_stay_out_of_metadata():
    for retired_table_name in _RETIRED_TABLE_NAMES:
        assert retired_table_name not in db_models.Base.metadata.tables, (
            f"{retired_table_name!r} belongs to the retired parallel email "
            "model; email_records is the single source of truth "
            "(docs/engineering/email-model-reconciliation.md)"
        )


def test_retired_parallel_email_models_stay_removed():
    for retired_class_name in _RETIRED_MODEL_CLASS_NAMES:
        assert not hasattr(db_models, retired_class_name), (
            f"db.models.{retired_class_name} belongs to the retired parallel "
            "email model; do not reintroduce it "
            "(docs/engineering/email-model-reconciliation.md)"
        )


def test_email_source_of_truth_tables_present():
    for live_table_name in (
        "email_records",
        "email_attachments",
        "image_sources",
        "tenant_configs",
        "caldav_accounts",
        "webdav_accounts",
    ):
        assert live_table_name in db_models.Base.metadata.tables
