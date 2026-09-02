"""Regression contract for evidence-based sender relationship decisions."""

import pytest

from services.ontology_service import OntologyService, RelationshipClassificationUnavailable


def test_content_and_sender_names_cannot_synthesize_relationship_type_or_confidence() -> None:
    service = OntologyService()
    with pytest.raises(RelationshipClassificationUnavailable):
        service.analyze_sender_relationship(
            "owner@company.example",
            "newsletter@marketing.example",
            "Please unsubscribe. Invoice and renewal details follow.",
        )


def test_same_domain_is_not_relationship_ground_truth() -> None:
    service = OntologyService()
    with pytest.raises(RelationshipClassificationUnavailable):
        service.analyze_sender_relationship(
            "owner@company.example",
            "unknown@company.example",
            "Hello",
        )


def test_relationship_label_cannot_trigger_local_priority_action_policy() -> None:
    service = OntologyService()
    newsletter = service.next_action_for_relationship("Newsletter")
    vendor = service.next_action_for_relationship("Vendor")
    assert newsletter == vendor == {
        "next_action": "unavailable",
        "action_reason": "No validated relationship action policy is configured.",
    }
