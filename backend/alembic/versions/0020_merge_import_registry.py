"""Join the retained import ownership and workspace registry histories.

Neither parent is replaced: both upgrades must run before import validation.
"""

revision = "0020_merge_import_registry"
down_revision = (
    "0019_merge_read_state_ownership",
    "0019_email_read_state_repair",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join both parent revisions without changing customer data."""


def downgrade() -> None:
    """Restore the two parent heads without undoing their schema objects."""
