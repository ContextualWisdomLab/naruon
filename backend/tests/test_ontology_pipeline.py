import pytest
from unittest.mock import AsyncMock, MagicMock

from db.models import Email
from services.email_service import process_self_to_self
from services.ontology_service import (
    OntologyService,
    RelationshipClassificationUnavailable,
    RelationshipData,
)


@pytest.mark.asyncio
async def test_sender_relationship_insertion_requires_validated_classification():
    ontology_service = OntologyService()
    session_mock = AsyncMock()
    session_mock.add = MagicMock()

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = execute_result

    with pytest.raises(RelationshipClassificationUnavailable):
        await ontology_service.save_relationship(
            session_mock,
            data=RelationshipData(
                user_email="user@test.com",
                sender_email="colleague@test.com",
                email_content="Hey let's talk about the project",
                user_id="user_1",
                organization_id="org_1",
                source_message_id="<project@test.com>",
                source_thread_id="thread-project",
            ),
        )

    session_mock.add.assert_not_called()


@pytest.mark.asyncio
async def test_self_to_self_triggers_knowledge_extraction():
    ontology_service = OntologyService()
    session_mock = AsyncMock()
    session_mock.add = MagicMock()

    email_data = {
        "sender": "user@test.com",
        "recipients": ["user@test.com"],
        "subject": "Note to self",
        "body": "Remember to buy milk",
    }

    is_self = process_self_to_self(email_data, "user@test.com")
    assert is_self is True

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
    assert knowledge_task.source_type == "self_sent_knowledge"
    assert knowledge_task.related_email_id == 44
