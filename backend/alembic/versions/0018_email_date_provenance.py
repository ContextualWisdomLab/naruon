"""add date_provenance to email_records

Revision ID: 0018_email_date_provenance
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-07-30 00:00:00.000000

Records the provenance of each stored email ``date`` so a synthetic
collection-time fallback (missing/invalid RFC822 Date header) is never treated
as original sender metadata when seeding a strong auto-dedupe fingerprint
(naruon#1086). Nullable-free with a ``"unknown"`` server default so existing
rows backfill safely: their date provenance is genuinely unknown, and only
``"parsed"`` rows are eligible to seed a strong fingerprint, so the backfill is
conservative (it can only widen review, never manufacture a duplicate).
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_date_provenance"
down_revision = "0017_merge_newsdom_carddav_heads"

_EMAIL_TABLE = "email_records"
_PROVENANCE_COLUMN = "date_provenance"


def upgrade() -> None:
    """Add the ``date_provenance`` column, backfilling existing rows to unknown."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(_EMAIL_TABLE)}
    if _PROVENANCE_COLUMN not in columns:
        op.add_column(
            _EMAIL_TABLE,
            sa.Column(
                _PROVENANCE_COLUMN,
                sa.String(),
                nullable=False,
                server_default="unknown",
            ),
        )


def downgrade() -> None:
    """Drop the ``date_provenance`` column if present."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(_EMAIL_TABLE)}
    if _PROVENANCE_COLUMN in columns:
        op.drop_column(_EMAIL_TABLE, _PROVENANCE_COLUMN)
