import pytest

from services.ontology_service import (
    RelationshipClassificationUnavailable,
    ontology_service,
)


@pytest.mark.parametrize(
    ("user_email", "sender_email", "content"),
    [
        (
            "seongho@company.com",
            "newsletter@marketing.com",
            "Please unsubscribe here",
        ),
        ("seongho@company.com", "boss@company.com", "Hello"),
        ("seongho@company.com", "Boss@Company.com", "Hello"),
    ],
)
def test_analyze_sender_relationship_abstains_without_validated_model(
    user_email: str,
    sender_email: str,
    content: str,
) -> None:
    with pytest.raises(RelationshipClassificationUnavailable):
        ontology_service.analyze_sender_relationship(user_email, sender_email, content)


@pytest.mark.parametrize(
    ("user_email", "sender_email", "content"),
    [
        (
            "buyer@company.com",
            "billing@saas.example",
            "Invoice and payment receipt for your subscription renewal.",
        ),
        (
            "seller@company.com",
            "lead@customer.example",
            "Please review the proposal, pricing, and statement of work.",
        ),
        (
            "operator@company.com",
            "ops@vendor.example",
            "Can you confirm the implementation window?",
        ),
    ],
)
def test_business_terms_and_domains_are_not_relationship_ground_truth(
    user_email: str,
    sender_email: str,
    content: str,
) -> None:
    with pytest.raises(RelationshipClassificationUnavailable):
        ontology_service.analyze_sender_relationship(user_email, sender_email, content)
