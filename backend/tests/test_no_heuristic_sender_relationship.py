"""Regression contract for evidence-based sender relationship classification."""

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
