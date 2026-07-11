import logging
from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any, Dict
from sqlalchemy import select
from db.models import Email, SenderRelationship
from services.email_service import process_self_to_self
from services.knowledge_extractor import extract_knowledge_from_self_sent

logger = logging.getLogger(__name__)

NEWSLETTER_TERMS = (
    "unsubscribe",
    "view in browser",
    "manage preferences",
    "newsletter",
    "mailing list",
)
NEWSLETTER_LOCAL_PARTS = ("newsletter", "news", "updates", "digest", "noreply", "no-reply")
VENDOR_TERMS = (
    "invoice",
    "receipt",
    "payment",
    "billing",
    "subscription",
    "shipment",
    "support ticket",
    "service renewal",
    "purchase order",
)
VENDOR_LOCAL_PARTS = ("billing", "invoice", "support", "orders", "accounts", "vendor")
CLIENT_TERMS = (
    "proposal",
    "contract",
    "statement of work",
    "sow",
    "deliverable",
    "pricing",
    "renewal",
    "budget approval",
    "kickoff",
)
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "outlook.com",
    "yahoo.com",
}


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
    def __init__(self):
        self.relationships = {}

    def next_action_for_relationship(self, relationship_type: str) -> Dict[str, str]:
        normalized_type = relationship_type.strip().lower()
        if normalized_type == "newsletter":
            return {
                "next_action": "summarize_then_archive",
                "action_reason": "Bulk sender; summarize signal before lowering priority.",
            }
        if normalized_type == "colleague":
            return {
                "next_action": "track_reply_and_tasks",
                "action_reason": "Same-domain sender; preserve reply and task follow-up.",
            }
        if normalized_type in {"client", "vendor"}:
            return {
                "next_action": "prepare_response_draft",
                "action_reason": "External business sender; keep response intent visible.",
            }
        return {
            "next_action": "classify_sender",
            "action_reason": "Relationship is unknown; capture more evidence first.",
        }

    def analyze_sender_relationship(
        self, user_email: str, sender_email: str, email_content: str
    ) -> Dict[str, Any]:
        """
        Analyze content to build the user's sender relationship graph.
        """
        relationship_type = "Unknown"
        confidence = 0.5
        signals: list[str] = []
        content = email_content.lower()
        user_domain = _email_domain(user_email)
        sender_domain = _email_domain(sender_email)
        sender_local = _email_local_part(sender_email)

        if _contains_any(content, NEWSLETTER_TERMS) or sender_local in NEWSLETTER_LOCAL_PARTS:
            relationship_type = "Newsletter"
            confidence = 0.9
            signals.append("bulk_sender")
        elif user_domain and sender_domain and user_domain == sender_domain:
            relationship_type = "Colleague"
            confidence = 0.85
            signals.append("same_domain")
        else:
            vendor_score = _term_score(content, VENDOR_TERMS) + int(
                sender_local in VENDOR_LOCAL_PARTS
            )
            client_score = _term_score(content, CLIENT_TERMS)
            if vendor_score > client_score and vendor_score > 0:
                relationship_type = "Vendor"
                confidence = min(0.95, 0.72 + (vendor_score * 0.06))
                signals.append("vendor_commercial_terms")
            elif client_score > 0:
                relationship_type = "Client"
                confidence = min(0.92, 0.7 + (client_score * 0.06))
                signals.append("client_commercial_terms")
            elif sender_domain and sender_domain not in PERSONAL_EMAIL_DOMAINS:
                relationship_type = "Vendor"
                confidence = 0.62
                signals.append("external_business_domain")

        action = self.next_action_for_relationship(relationship_type)
        logger.info(
            "Analyzed sender relationship %s as %s with confidence %.2f using %s",
            sender_email,
            relationship_type,
            confidence,
            ",".join(signals) or "no_signal",
        )
        return {
            "type": relationship_type,
            "confidence": confidence,
            "signals": signals,
            **action,
        }

    async def save_relationship(
        self,
        session,
        data: RelationshipData,
    ):
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


def _email_domain(address: str) -> str | None:
    _, separator, domain = address.strip().lower().rpartition("@")
    return domain if separator and domain else None


def _email_local_part(address: str) -> str:
    local_part, _, _ = address.strip().lower().partition("@")
    return local_part


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _term_score(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


ontology_service = OntologyService()
