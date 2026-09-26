import pytest
from db.models import Email, TicketTask
from services.knowledge_extractor import extract_knowledge_from_self_sent
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock


class _ScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _make_email(**overrides):
    values = {
        "id": 1,
        "user_id": "testuser",
        "organization_id": "testorg",
        "message_id": "msg1",
        "thread_id": "thread1",
        "sender": "Test User <testuser@example.com>",
        "recipients": "testuser@example.com",
        "subject": "Buy milk",
        "body": "Don't forget to buy milk later.",
    }
    values.update(overrides)
    return Email(**values)


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent():
    # Mock db session
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    
    # Mock self-sent email
    email = _make_email()
    
    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )
    
    assert task is not None
    assert task.title == "Memo: Buy milk"
    assert task.source_type == "self_sent_knowledge"
    assert task.related_email_id == 1
    assert task.related_thread_id == "thread1"
    
    # The caller owns the transaction so the email and note can roll back together.
    db.add.assert_called_once_with(task)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_skips_non_self_address():
    db = AsyncMock(spec=AsyncSession)
    email = _make_email(recipients="teammate@example.com")

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is None
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_skips_mixed_recipient_message():
    db = AsyncMock(spec=AsyncSession)
    email = _make_email(recipients="testuser@example.com, teammate@example.com")

    assert await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    ) is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_accepts_owner_alias_recipient():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    email = _make_email(recipients="alias@example.com")

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com", "alias@example.com"]
    )

    assert task is not None
    assert task.source_type == "self_sent_knowledge"
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_reuses_existing_task():
    db = AsyncMock(spec=AsyncSession)
    existing_task = TicketTask(
        user_id="testuser",
        organization_id="testorg",
        title="Memo: Buy milk",
        status="open",
        priority="normal",
        source_type="self_sent_knowledge",
        related_email_id=1,
        related_thread_id="thread1",
    )
    db.execute.return_value = _ScalarResult(existing_task)

    task = await extract_knowledge_from_self_sent(
        db, _make_email(), ["testuser@example.com"]
    )

    assert task is existing_task
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_sanitizes_markup_title():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    email = _make_email(
        subject="<script>alert('x')</script>Quarter plan",
        body="<h1>Quarter plan</h1>",
    )

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is not None
    assert task.title == "Memo: Quarter plan"
    assert "<" not in task.title
    assert "script" not in task.title.lower()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_requires_tenant_owned_address():
    db = AsyncMock(spec=AsyncSession)
    email = _make_email(
        sender="Other User <other@example.com>",
        recipients="other@example.com",
    )

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is None
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_allows_subject_only_note():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    email = _make_email(body="")

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is not None
    assert task.title == "Memo: Buy milk"


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_accepts_single_owner_address_string():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()

    task = await extract_knowledge_from_self_sent(
        db, _make_email(), "testuser@example.com"
    )

    assert task is not None
    assert task.related_email_id == 1


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_rejects_empty_owner_addresses():
    db = AsyncMock(spec=AsyncSession)

    task = await extract_knowledge_from_self_sent(db, _make_email(), [])

    assert task is None
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_uses_user_id_email_fallback():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    email = _make_email(
        user_id="testuser@example.com",
        sender="Test User <testuser@example.com>",
        recipients="testuser@example.com",
    )

    task = await extract_knowledge_from_self_sent(db, email)

    assert task is not None
    assert task.user_id == "testuser@example.com"
    assert task.related_email_id == 1


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_rejects_empty_sender():
    db = AsyncMock(spec=AsyncSession)
    email = _make_email(sender="")

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is None
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_uses_plain_text_body_title():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult()
    email = _make_email(
        subject="  ",
        body="<h1>Quarter plan</h1>\n<script>alert('x')</script>",
    )

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is not None
    assert task.title == "Memo: Quarter plan"
    assert "<" not in task.title
    assert "script" not in task.title.lower()


@pytest.mark.asyncio
async def test_extract_knowledge_from_self_sent_skips_unsaved_email():
    db = AsyncMock(spec=AsyncSession)
    email = _make_email(id=None)

    task = await extract_knowledge_from_self_sent(
        db, email, ["testuser@example.com"]
    )

    assert task is None
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
