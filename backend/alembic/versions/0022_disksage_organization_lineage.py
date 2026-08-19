"""persist path-free DiskSage organization lineage batches"""

from alembic import op
import sqlalchemy as sa


revision = "0022_disksage_org_lineage"
down_revision = "0021_disksage_scope_idx"
branch_labels = None
depends_on = None

_TABLE = "disksage_organization_lineage_records"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("organization_lineage_record_uid", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("batch_fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("envelope_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("ontology_classes", sa.JSON(), nullable=False),
        sa.Column("envelope_json_encrypted", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("organization_lineage_record_uid"),
        sa.UniqueConstraint(
            "user_id",
            "workspace_id",
            "batch_fingerprint_sha256",
            name="uq_disksage_org_lineage_workspace_fingerprint",
        ),
    )
    op.create_index(
        "ix_disksage_org_lineage_scope_time",
        _TABLE,
        ["user_id", "workspace_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_disksage_org_lineage_scope_time", table_name=_TABLE, if_exists=True)
    if sa.inspect(op.get_bind()).has_table(_TABLE):
        op.drop_table(_TABLE)
