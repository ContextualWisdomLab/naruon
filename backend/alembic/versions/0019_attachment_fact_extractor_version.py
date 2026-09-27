"""Track durable attachment inference completion independently of recognition."""

from alembic import op
import sqlalchemy as sa

revision = "0019_attachment_fact_version"
down_revision = "0018_attachment_filename_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "fact_extractor_version" not in {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("email_attachments")
    }:
        op.add_column(
            "email_attachments",
            sa.Column("fact_extractor_version", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("email_attachments", "fact_extractor_version")
