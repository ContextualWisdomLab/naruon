import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.models import Email
from db.session import get_db

router = APIRouter(prefix="/api/network")


class NetworkGraphNode(BaseModel):
    """One email-identity node in the organization communication graph."""

    node_id: str = Field(alias="id")
    node_label: str = Field(alias="label")

    model_config = {"populate_by_name": True}


class NetworkGraphEdge(BaseModel):
    """One directed sender-to-recipient relationship in the network graph."""

    source_node_id: str = Field(alias="source")
    target_node_id: str = Field(alias="target")
    edge_weight: int = Field(alias="weight")

    model_config = {"populate_by_name": True}


class NetworkGraphResponse(BaseModel):
    """Network graph payload with semantic internal names and stable wire aliases."""

    network_nodes: list[NetworkGraphNode] = Field(alias="nodes")
    network_edges: list[NetworkGraphEdge] = Field(alias="edges")

    model_config = {"populate_by_name": True}


EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def extract_emails(text: str | None) -> list[str]:
    """Extract email addresses from one sender or recipient text value."""
    if not text:
        return []
    return EMAIL_PATTERN.findall(text)


@router.get("/graph", response_model=NetworkGraphResponse)
async def get_network_graph(
    email_record_limit: int = Query(default=500, ge=1, le=2000, alias="limit"),
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """Return the caller-scoped email communication graph without changing wire keys."""
    current_user = auth_context.user_id
    if user_id and user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized")
    target_user_id = user_id or current_user
    organization_filter = (
        Email.organization_id == auth_context.organization_id
        if auth_context.organization_id is not None
        else Email.organization_id.is_(None)
    )

    result = await db.execute(
        select(Email.sender, Email.recipients)
        .where(Email.user_id == target_user_id, organization_filter)
        .limit(email_record_limit)
    )
    rows = result.fetchall()

    nodes_set = set()
    edges_dict = {}  # (sender, recipient) -> weight

    nodes_add = nodes_set.add
    edges_get = edges_dict.get
    findall = EMAIL_PATTERN.findall

    for row in rows:
        sender_str = row[0]
        recipients_str = row[1]

        sender_email = None
        if sender_str:
            senders = findall(sender_str.lower())
            if senders:
                sender_email = senders[0]
                nodes_add(sender_email)

        if recipients_str:
            recipients = findall(recipients_str.lower())
            if recipients:
                nodes_set.update(recipients)
                if sender_email:
                    for rec_email in recipients:
                        if sender_email != rec_email:
                            edge_key = (sender_email, rec_email)
                            edges_dict[edge_key] = edges_get(edge_key, 0) + 1

    network_nodes = [
        NetworkGraphNode(node_id=email, node_label=email) for email in nodes_set
    ]
    network_edges = [
        NetworkGraphEdge(
            source_node_id=source_email,
            target_node_id=target_email,
            edge_weight=edge_weight,
        )
        for (source_email, target_email), edge_weight in edges_dict.items()
    ]

    return NetworkGraphResponse(
        network_nodes=network_nodes,
        network_edges=network_edges,
    )
