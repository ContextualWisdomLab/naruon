"""Join provenance identity and workspace repair histories without rewriting either."""

revision = "0020_merge_provenance_workspace"
down_revision = ("0018_provenance_identity", "0019_email_read_state_repair")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Require both existing branches before recording the unified head."""
    return None


def downgrade() -> None:
    """Reopen the two revision heads without changing customer records."""
    return None
