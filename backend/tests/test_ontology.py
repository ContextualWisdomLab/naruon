from services.ontology_service import ontology_service

def test_analyze_sender_relationship():
    result1 = ontology_service.analyze_sender_relationship("seongho@company.com", "newsletter@marketing.com", "Please unsubscribe here")
    assert result1["type"] == "Newsletter"
    assert result1["confidence"] == 0.9
    assert result1["next_action"] == "summarize_then_archive"

    result2 = ontology_service.analyze_sender_relationship("seongho@company.com", "boss@company.com", "Hello")
    assert result2["type"] == "Colleague"
    assert result2["confidence"] == 0.85
    assert result2["next_action"] == "track_reply_and_tasks"

    result3 = ontology_service.analyze_sender_relationship("seongho@company.com", "Boss@Company.com", "Hello")
    assert result3["type"] == "Colleague"
    assert result3["confidence"] == 0.85
    assert result3["next_action"] == "track_reply_and_tasks"
