"""persist scoped, encrypted DiskSage file lineage envelopes

Revision ID: 0018_disksage_file_lineage
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-13 00:00:00.000000

The Rust DiskSage verifier remains authoritative for copy/provider proof. Naruon
stores the validated envelope for workspace-scoped provenance and exposes only
the redacted graph projection in list responses.
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_disksage_file_lineage"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TABLE = "disksage_file_lineage_records"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("lineage_record_uid", sa.String(length=96), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("lineage_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("envelope_sha256", sa.String(length=64), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False),
            sa.Column("schema_kind", sa.String(length=96), nullable=False),
            sa.Column("source_kind", sa.String(length=64), nullable=False),
            sa.Column("archive_kind", sa.String(length=64), nullable=False),
            sa.Column("raw_content_sha256", sa.String(length=64), nullable=False),
            sa.Column("raw_content_blake3", sa.String(length=64), nullable=False),
            sa.Column("content_bytes", sa.BigInteger(), nullable=False),
            sa.Column("ontology_class", sa.String(length=256), nullable=False),
            sa.Column("ontology_relation_count", sa.Integer(), nullable=False),
            sa.Column("ontology_predicates", sa.JSON(), nullable=False),
            sa.Column("provider_name", sa.String(length=32), nullable=False),
            sa.Column("provider_sync_confirmed", sa.Boolean(), nullable=False),
            sa.Column(
                "provider_sync_state",
                sa.String(length=32),
                nullable=False,
                server_default="unknown",
            ),
            sa.Column("envelope_json_encrypted", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("lineage_record_uid"),
            sa.UniqueConstraint(
                "user_id",
                "workspace_id",
                "lineage_fingerprint",
                name="uq_disksage_lineage_workspace_fingerprint",
            ),
        )

    op.create_index(
        "ix_disksage_lineage_scope_time",
        _TABLE,
        ["user_id", "organization_id", "workspace_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_disksage_lineage_ontology_class",
        _TABLE,
        ["workspace_id", "ontology_class"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_disksage_lineage_ontology_class", table_name=_TABLE, if_exists=True
    )
    op.drop_index("ix_disksage_lineage_scope_time", table_name=_TABLE, if_exists=True)
    connection = op.get_bind()
    if sa.inspect(connection).has_table(_TABLE):
        op.drop_table(_TABLE)
