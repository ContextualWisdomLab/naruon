import pytest

from db.models import Document
from tests.test_data_api import (
    _now,
    _restore_overrides,
    _signed_session_token,
    _valid_session_payload,
    _with_signed_auth,
    mock_db as _data_api_mock_db,
)


@pytest.fixture
def mock_db():
    """Reuse the data-quality API session fixture in this focused module."""
    return _data_api_mock_db.__wrapped__()


def test_data_quality_surface_excludes_cross_org_document_in_same_workspace(mock_db):
    mock_db.documents.extend(
        [
            Document(
                document_id="doc_owned_same_workspace",
                workspace_id="workspace-org-acme",
                organization_id="org-acme",
                document_name="owned.md",
                document_type="text/markdown",
                document_content="owned",
                document_status="uploaded",
                created_at=_now(),
            ),
            Document(
                document_id="doc_rival_same_workspace",
                workspace_id="workspace-org-acme",
                organization_id="org-rival",
                document_name="rival.md",
                document_type="text/markdown",
                document_content="rival",
                document_status="uploaded",
                created_at=_now(),
            ),
        ]
    )
    token = _signed_session_token(_valid_session_payload())
    client, previous_secret, original_overrides = _with_signed_auth(mock_db, token)
    try:
        response = client.get("/api/data/quality-surface")
    finally:
        client.close()
        _restore_overrides(previous_secret, original_overrides)

    assert response.status_code == 200, response.text
    data = response.json()
    document_repository = next(
        repository
        for repository in data["repositories"]
        if repository["repository_type"] == "document_repository"
    )
    assert document_repository["object_count"] == 1
    document_asset_keys = {
        asset["asset_key"]
        for asset in data["repository_assets"]
        if asset["asset_type"] == "workspace_document"
    }
    assert document_asset_keys == {"doc_owned_same_workspace"}
