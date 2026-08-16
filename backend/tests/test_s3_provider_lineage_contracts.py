"""Red-green contracts for provider revisions and single-active authority."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from api.object_storage_providers import ObjectStorageProviderUpdate
from db.object_storage_provider import ObjectStorageProvider


def test_provider_update_rejects_storage_topology_changes() -> None:
    """Existing object locators must not be rebound to a different storage topology."""
    forbidden_updates = [
        {"bucket_name": "different-bucket"},
        {"region_name": "eu-west-1"},
        {"endpoint_url": "https://objects.example.com"},
        {"addressing_style": "path"},
        {"server_side_encryption": "aws:kms"},
        {"kms_key_id": "different-key"},
        {"expected_bucket_owner": "111122223333"},
    ]
    for update in forbidden_updates:
        with pytest.raises(ValidationError):
            ObjectStorageProviderUpdate(**update)


def test_provider_update_allows_only_identity_safe_rotation_fields() -> None:
    """Names, credentials, session tokens, and activation may rotate in place."""
    update = ObjectStorageProviderUpdate(
        provider_name="rotated-credentials",
        access_key_id="new-access-key",
        secret_access_key="new-secret-key",
        session_token="new-session-token",
        is_active=True,
    )
    assert update.model_dump(exclude_unset=True) == {
        "provider_name": "rotated-credentials",
        "access_key_id": "new-access-key",
        "secret_access_key": "new-secret-key",
        "session_token": "new-session-token",
        "is_active": True,
    }


def test_provider_table_enforces_one_active_row_per_organization() -> None:
    """Concurrent API requests must not create two active providers for one org."""
    qualifying_indexes = [
        index
        for index in ObjectStorageProvider.__table__.indexes
        if index.unique
        and {column.name for column in index.columns} == {"organization_id"}
        and index.dialect_options["postgresql"].get("where") is not None
    ]
    assert [index.name for index in qualifying_indexes] == [
        "uq_object_storage_providers_active_org"
    ]
