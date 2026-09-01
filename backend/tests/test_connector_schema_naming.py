"""Naming-contract regressions for self-hosted connector schemas."""

from schema.connector import (
    SelfHostedConnectorRegistrationRequest,
    SelfHostedConnectorRegistrationResponse,
)


def test_connector_registration_request_uses_semantic_owned_names() -> None:
    """Keep generic wire aliases at the boundary, not as owned model vocabulary."""
    assert "connector_capabilities" in SelfHostedConnectorRegistrationRequest.model_fields
    assert "capabilities" not in SelfHostedConnectorRegistrationRequest.model_fields

    request = SelfHostedConnectorRegistrationRequest.model_validate(
        {
            "connector_id": "connector-1",
            "public_key": "public-key",
            "supported_protocols": ["imap"],
            "capabilities": ["mail_read"],
        }
    )

    assert request.connector_capabilities == ["mail_read"]
    assert request.model_dump(by_alias=True)["capabilities"] == ["mail_read"]


def test_connector_registration_response_uses_semantic_owned_status_name() -> None:
    """Preserve the legacy status wire key while owning registration_status internally."""
    assert "registration_status" in SelfHostedConnectorRegistrationResponse.model_fields
    assert "status" not in SelfHostedConnectorRegistrationResponse.model_fields

    response = SelfHostedConnectorRegistrationResponse.model_validate(
        {
            "connector_id": "connector-1",
            "status": "pending_approval",
            "issued_certificate": None,
            "endpoint_url": "https://connector.example.test",
        }
    )

    assert response.registration_status == "pending_approval"
    assert response.model_dump(by_alias=True)["status"] == "pending_approval"
