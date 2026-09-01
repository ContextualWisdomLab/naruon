from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SelfHostedConnectorRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    connector_id: str = Field(..., description="Unique identifier for the self-hosted connector")
    public_key: str = Field(..., description="Public key for mTLS or secure payload exchange")
    supported_protocols: list[
        Literal["imap", "smtp", "pop3", "caldav", "carddav", "webdav"]
    ] = Field(
        default_factory=list, description="Protocols supported by this connector instance"
    )
    connector_capabilities: list[str] = Field(default_factory=list, alias="capabilities")


class SelfHostedConnectorRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    connector_id: str
    registration_status: Literal["pending_approval", "active", "rejected"] = Field(
        alias="status"
    )
    issued_certificate: str | None = None
    endpoint_url: str


class OIDCGatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str
    issuer_url: str
    client_id: str
    audience: str
    required_scopes: list[str]
    enforce_rbac_sync: bool = True
