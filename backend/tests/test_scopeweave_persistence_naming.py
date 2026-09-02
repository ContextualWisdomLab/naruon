"""Regression coverage for semantic ScopeWeave persistence identifiers."""

from pathlib import Path

from db.models import ScopeweavePromotionLink, ScopeweavePromotionTarget


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_scopeweave_orm_primary_keys_use_bounded_context_names():
    """ScopeWeave-owned ORM primary keys must not expose a generic ``id`` field."""
    target_columns = ScopeweavePromotionTarget.__table__.columns
    link_columns = ScopeweavePromotionLink.__table__.columns

    assert "id" not in target_columns
    assert "scopeweave_promotion_target_id" in target_columns
    assert ScopeweavePromotionTarget.__table__.primary_key.columns.keys() == [
        "scopeweave_promotion_target_id"
    ]

    assert "id" not in link_columns
    assert "scopeweave_promotion_link_id" in link_columns
    assert ScopeweavePromotionLink.__table__.primary_key.columns.keys() == [
        "scopeweave_promotion_link_id"
    ]


def test_scopeweave_primary_key_migration_is_reversible_and_head_safe():
    """A forward Alembic revision must preserve old rows while renaming both PKs."""
    migration_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0018_scopeweave_semantic_ids.py"
    )
    assert migration_path.exists()
    migration_text = migration_path.read_text()

    assert 'revision = "0018_scopeweave_semantic_ids"' in migration_text
    assert 'down_revision = "0017_merge_newsdom_carddav_heads"' in migration_text
    assert '"scopeweave_promotion_target"' in migration_text
    assert '"scopeweave_promotion_link"' in migration_text
    assert '"scopeweave_promotion_target_id"' in migration_text
    assert '"scopeweave_promotion_link_id"' in migration_text
    assert 'new_column_name="scopeweave_promotion_target_id"' in migration_text
    assert 'new_column_name="scopeweave_promotion_link_id"' in migration_text
    assert 'new_column_name="id"' in migration_text
    assert "op.alter_column(" in migration_text
    assert "op.drop_column(" not in migration_text
    assert "op.add_column(" not in migration_text
