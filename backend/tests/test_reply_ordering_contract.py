"""Regression contracts for deterministic email-thread reply ordering."""

import datetime
from types import SimpleNamespace

import pytest

from api import emails as emails_api
from db.models import Email
from services.reply_tracking_service import thread_reply_candidate


USER_ADDRESSES = {"me@example.com"}
EQUAL_DATE = datetime.datetime(2026, 8, 7, 0, 0, tzinfo=datetime.timezone.utc)


class _EmptyScalarsResult:
    """Minimal SQLAlchemy-result stand-in returning no selected thread heads."""

    def scalars(self):
        """Return this result as the scalar-result facade."""
        return self

    def all(self):
        """Return an empty result set."""
        return []


class _QueryCapturingSession:
    """Capture executed statements while returning an empty mailbox."""

    def __init__(self) -> None:
        self.queries: list[object] = []

    async def execute(self, query, params=None):
        """Record one statement and return an empty scalar result."""
        del params
        self.queries.append(query)
        return _EmptyScalarsResult()


def _sent_email(message_id: str, email_id: int) -> Email:
    """Build one equal-date sent message with a deterministic database id."""
    return Email(
        id=email_id,
        user_id="user_1",
        organization_id="org_1",
        message_id=message_id,
        thread_id="thread_1",
        sender="me@example.com",
        recipients="client@example.com",
        subject="Reply ordering",
        date=EQUAL_DATE,
        body="Please reply.",
    )


@pytest.mark.asyncio
async def test_get_emails_orders_ranked_heads_by_date_then_id(monkeypatch) -> None:
    """Equal-date thread heads must have deterministic page membership by id."""

    async def _tenant_config(_db, _user_id, _organization_id):
        return None

    monkeypatch.setattr(emails_api, "get_scoped_tenant_config", _tenant_config)
    session = _QueryCapturingSession()

    response = await emails_api.get_emails(
        limit=1,
        folder="inbox",
        db=session,
        auth_context=SimpleNamespace(user_id="user_1", organization_id="org_1"),
    )

    assert response == {"emails": []}
    assert len(session.queries) == 1
    query_text = str(session.queries[0]).lower()
    assert "order by email_records.date desc, email_records.id desc" in query_text


def test_descending_reply_candidate_matches_default_equal_date_tie_break() -> None:
    """The trusted descending fast path must match the default `(date, id)` sort."""
    lower_id = _sent_email("sent-low", 1)
    higher_id = _sent_email("sent-high", 2)

    default_candidate = thread_reply_candidate(
        [lower_id, higher_id],
        USER_ADDRESSES,
    )
    descending_candidate = thread_reply_candidate(
        [higher_id, lower_id],
        USER_ADDRESSES,
        is_descending=True,
    )

    assert default_candidate is higher_id
    assert descending_candidate is default_candidate
