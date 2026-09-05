"""Join provenance identity and workspace repair histories without rewriting either."""

revision = "0021_merge_provenance_workspace"
down_revision = ("0018_provenance_identity", "0020_search_trigram_storage")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Require both existing branches before recording the unified head."""
    return None


def downgrade() -> None:
    """Reopen the two revision heads without changing customer records."""
    return None
