from services.ontology_service import ontology_service


def test_analyze_sender_relationship():
    result1 = ontology_service.analyze_sender_relationship(
        "seongho@company.com", "newsletter@marketing.com", "Please unsubscribe here"
    )
    assert result1["type"] == "Newsletter"
    assert result1["confidence"] == 0.9
    assert result1["next_action"] == "summarize_then_archive"

    result2 = ontology_service.analyze_sender_relationship(
        "seongho@company.com", "boss@company.com", "Hello"
    )
    assert result2["type"] == "Colleague"
    assert result2["confidence"] == 0.85
    assert result2["next_action"] == "track_reply_and_tasks"

    result3 = ontology_service.analyze_sender_relationship(
        "seongho@company.com", "Boss@Company.com", "Hello"
    )
    assert result3["type"] == "Colleague"
    assert result3["confidence"] == 0.85
    assert result3["next_action"] == "track_reply_and_tasks"


def test_analyze_sender_relationship_uses_business_signals():
    vendor = ontology_service.analyze_sender_relationship(
        "buyer@company.com",
        "billing@saas.example",
        "Invoice and payment receipt for your subscription renewal.",
    )
    assert vendor["type"] == "Vendor"
    assert vendor["confidence"] >= 0.78
    assert vendor["next_action"] == "prepare_response_draft"
    assert "vendor_commercial_terms" in vendor["signals"]

    client = ontology_service.analyze_sender_relationship(
        "seller@company.com",
        "lead@customer.example",
        "Please review the proposal, pricing, and statement of work.",
    )
    assert client["type"] == "Client"
    assert client["confidence"] >= 0.82
    assert client["next_action"] == "prepare_response_draft"
    assert "client_commercial_terms" in client["signals"]

    business_domain = ontology_service.analyze_sender_relationship(
        "operator@company.com",
        "ops@vendor.example",
        "Can you confirm the implementation window?",
    )
    assert business_domain["type"] == "Vendor"
    assert business_domain["confidence"] == 0.62
    assert business_domain["signals"] == ["external_business_domain"]
