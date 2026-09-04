import re

from api.auth import AuthContext, get_auth_context
from db.models import Email
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/network")


class NetworkGraphWireModel(BaseModel):
    """Translate specific Naruon graph names to the established JSON wire keys."""

    model_config = ConfigDict(populate_by_name=True)


class NetworkGraphNode(NetworkGraphWireModel):
    """Represent one email-address node with bounded-context-specific names."""

    node_id: str = Field(alias="id")
    node_label: str = Field(alias="label")


class NetworkGraphEdge(NetworkGraphWireModel):
    """Represent one directed email relationship and its observed message count."""

    source_node_id: str = Field(alias="source")
    target_node_id: str = Field(alias="target")
    message_count: int = Field(alias="weight")


class NetworkGraphResponse(NetworkGraphWireModel):
    """Return the network-graph collection without exposing generic internal names."""

    network_nodes: list[NetworkGraphNode] = Field(alias="nodes")
    network_edges: list[NetworkGraphEdge] = Field(alias="edges")


EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def extract_emails(email_text: str | None) -> list[str]:
    """Extract email addresses from one optional source string."""
    if not email_text:
        return []
    return EMAIL_PATTERN.findall(email_text)


@router.get(
    "/graph",
    response_model=NetworkGraphResponse,
    response_model_by_alias=True,
)
async def get_network_graph(
    email_limit: int = Query(default=500, ge=1, le=2000, alias="limit"),
    user_id: str | None = None,
    database_session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> NetworkGraphResponse:
    """Build the authenticated user's sender-recipient relationship graph."""
    current_user = auth_context.user_id
    if user_id and user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized")
    target_user_id = user_id or current_user
    organization_filter = (
        Email.organization_id == auth_context.organization_id
        if auth_context.organization_id is not None
        else Email.organization_id.is_(None)
    )

    email_query_result = await database_session.execute(
        select(Email.sender, Email.recipients)
        .where(Email.user_id == target_user_id, organization_filter)
        .limit(email_limit)
    )
    email_rows = email_query_result.fetchall()

    network_node_emails: set[str] = set()
    network_edge_counts: dict[tuple[str, str], int] = {}

    add_network_node = network_node_emails.add
    get_network_edge_count = network_edge_counts.get
    extract_email_addresses = EMAIL_PATTERN.findall

    for email_row in email_rows:
        sender_text = email_row[0]
        recipient_text = email_row[1]

        sender_email = None
        if sender_text:
            sender_addresses = extract_email_addresses(sender_text.lower())
            if sender_addresses:
                sender_email = sender_addresses[0]
                add_network_node(sender_email)

        if recipient_text:
            recipient_addresses = extract_email_addresses(recipient_text.lower())
            if recipient_addresses:
                network_node_emails.update(recipient_addresses)
                if sender_email:
                    for recipient_email in recipient_addresses:
                        if sender_email != recipient_email:
                            network_edge_key = (sender_email, recipient_email)
                            network_edge_counts[network_edge_key] = (
                                get_network_edge_count(network_edge_key, 0) + 1
                            )

    network_nodes = [
        NetworkGraphNode(node_id=email_address, node_label=email_address)
        for email_address in sorted(network_node_emails)
    ]
    network_edges = [
        NetworkGraphEdge(
            source_node_id=source_email,
            target_node_id=target_email,
            message_count=message_count,
        )
        for (source_email, target_email), message_count in sorted(
            network_edge_counts.items()
        )
    ]

    return NetworkGraphResponse(
        network_nodes=network_nodes,
        network_edges=network_edges,
    )
