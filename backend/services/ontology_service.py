import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy import select

from db.models import Email, SenderRelationship
from services.email_service import process_self_to_self
from services.knowledge_extractor import extract_knowledge_from_self_sent

logger = logging.getLogger(__name__)


class RelationshipClassificationUnavailable(RuntimeError):
    """Raised when sender relationship type/confidence lacks validated evidence."""


@dataclass
class RelationshipData:
    user_email: str
    sender_email: str
    email_content: str
    user_id: str
    organization_id: str | None = None
    source_message_id: str | None = None
    source_thread_id: str | None = None


class OntologyService:
    """Source-backed ontology operations with fail-closed relationship decisions."""

    def __init__(self):
        self.relationships = {}

    def next_action_for_relationship(self, relationship_type: str) -> Dict[str, str]:
        """Expose absence of a governed action policy without choosing a route."""
        return {
            "next_action": "unavailable",
            "action_reason": "No validated relationship action policy is configured.",
        }

    def analyze_sender_relationship(
        self, user_email: str, sender_email: str, email_content: str
    ) -> Dict[str, Any]:
        """Refuse to infer relationship type or confidence from local heuristics.

        Sender/local-part/domain identity, lexical content and term counts are
        observations, not calibrated relationship evidence. No replacement
        confidence or fallback class is synthesized when a validated classifier
        is unavailable.
        """
        raise RelationshipClassificationUnavailable(
            "automatic sender relationship classification is disabled until a "
            "validated measurement/classification model is available"
        )

    async def save_relationship(
        self,
        session,
        data: RelationshipData,
    ):
        """Persist a relationship only after governed classification exists.

        The current automatic classifier fails closed before any insert/update,
        preventing heuristic type/confidence values from entering durable state.
        """
        analysis = self.analyze_sender_relationship(
            data.user_email, data.sender_email, data.email_content
        )

        stmt = select(SenderRelationship).where(
            SenderRelationship.user_id == data.user_id,
            SenderRelationship.organization_id == data.organization_id,
            SenderRelationship.sender_email == data.sender_email,
            SenderRelationship.source_message_id == data.source_message_id,
            SenderRelationship.source_thread_id == data.source_thread_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.relationship_type = analysis["type"]
            existing.confidence_score = analysis["confidence"]
            existing.source_message_id = data.source_message_id
            existing.source_thread_id = data.source_thread_id
        else:
            new_rel = SenderRelationship(
                user_id=data.user_id,
                organization_id=data.organization_id,
                sender_email=data.sender_email,
                source_message_id=data.source_message_id,
                source_thread_id=data.source_thread_id,
                relationship_type=analysis["type"],
                confidence_score=analysis["confidence"],
            )
            session.add(new_rel)
        return analysis

    async def process_knowledge_node(
        self,
        session,
        email_data: dict,
        user_id: str,
        organization_id: str | None,
        owner_addresses: Iterable[str] | None = None,
        source_email: Email | None = None,
    ):
        """Extract source-backed self-sent knowledge without sender classification."""
        owner_address_list = _owner_address_list(owner_addresses)
        if not owner_address_list and "@" in str(user_id):
            owner_address_list = [str(user_id)]
        is_owner_self_sent = any(
            process_self_to_self(email_data, address) for address in owner_address_list
        )
        if not is_owner_self_sent:
            return None
        if source_email is None:
            logger.info(
                "Skipping self-sent knowledge extraction for user %s without source email row",
                user_id,
            )
            return None
        if (
            source_email.user_id != user_id
            or source_email.organization_id != organization_id
        ):
            return None
        return await extract_knowledge_from_self_sent(
            session, source_email, owner_address_list
        )


def _owner_address_list(owner_addresses: Iterable[str] | None) -> list[str]:
    if owner_addresses is None:
        return []
    if isinstance(owner_addresses, str):
        return [owner_addresses]
    return list(owner_addresses)


ontology_service = OntologyService()
