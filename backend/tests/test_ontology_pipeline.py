import pytest
from unittest.mock import AsyncMock, MagicMock
from db.models import Email, SenderRelationship
from services.ontology_service import OntologyService, RelationshipData

@pytest.mark.asyncio
async def test_sender_relationship_insertion():
    ontology_service = OntologyService()
    session_mock = AsyncMock()
    session_mock.add = MagicMock()
    
    # Assume select returns nothing (no existing relationship)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = execute_result
    
    relationship = await ontology_service.save_relationship(
        session_mock,
        data=RelationshipData(
            user_email="user@test.com",
            sender_email="colleague@test.com",
            email_content="Hey let's talk about the project",
            user_id="user_1",
            organization_id="org_1",
            source_message_id="<project@test.com>",
            source_thread_id="thread-project",
        )
    )
    
    session_mock.add.assert_called_once()
    added_rel = session_mock.add.call_args[0][0]
    assert isinstance(added_rel, SenderRelationship)
    assert added_rel.relationship_type == "Colleague"
    assert added_rel.user_id == "user_1"
    assert added_rel.organization_id == "org_1"
    assert added_rel.sender_email == "colleague@test.com"
    assert added_rel.source_message_id == "<project@test.com>"
    assert added_rel.source_thread_id == "thread-project"
    assert relationship["next_action"] == "track_reply_and_tasks"

@pytest.mark.asyncio
async def test_self_to_self_triggers_knowledge_extraction():
    # If the user sends an email to themselves, we want to extract knowledge
    from services.email_service import process_self_to_self
    ontology_service = OntologyService()
    session_mock = AsyncMock()
    session_mock.add = MagicMock()
    
    email_data = {
        "sender": "user@test.com",
        "recipients": ["user@test.com"],
        "subject": "Note to self",
        "body": "Remember to buy milk"
    }
    
    is_self = process_self_to_self(email_data, "user@test.com")
    assert is_self is True
    
    # Check that ontology_service handles self-sent knowledge only when a
    # source email row is available for provenance.
    source_email = Email(
        id=44,
        user_id="user_1",
        organization_id="org_1",
        message_id="<self-note@test.com>",
        thread_id="self-thread",
        sender="user@test.com",
        recipients="user@test.com",
        subject="Note to self",
        body="Remember to buy milk",
        is_personal_reference=True,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = execute_result

    knowledge_task = await ontology_service.process_knowledge_node(
        session_mock,
        email_data,
        user_id="user_1",
        organization_id="org_1",
        owner_addresses=["user@test.com"],
        source_email=source_email,
    )
    assert knowledge_task is not None
    assert await ontology_service.process_knowledge_node(
        session_mock,
        {**email_data, "is_automated_or_list": True},
        user_id="user_1",
        organization_id="org_1",
        owner_addresses=["user@test.com"],
        source_email=source_email,
    ) is None
    assert knowledge_task.source_type == "self_sent_knowledge"
    assert knowledge_task.related_email_id == 44
