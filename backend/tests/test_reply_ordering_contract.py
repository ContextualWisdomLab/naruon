"""Regression contracts for deterministic email-thread reply ordering."""

import datetime
from types import SimpleNamespace

import pytest

from api import emails as emails_api
from db.models import Email
from services.reply_tracking_service import (
    thread_reply_candidate,
    thread_requires_reply,
)


USER_ADDRESSES = {"me@example.com"}
EQUAL_DATE = datetime.datetime(2026, 8, 15, 0, 0, tzinfo=datetime.timezone.utc)


class _ScalarsResult:
    """Minimal SQLAlchemy-result stand-in for deterministic email rows."""

    def __init__(self, rows: list[Email]) -> None:
        """Retain the rows exposed through the scalar-result facade."""
        self._rows = rows

    def scalars(self):
        """Return this result as the scalar-result facade."""
        return self

    def all(self):
        """Return the deterministic result rows."""
        return self._rows


class _QueryCapturingSession:
    """Capture statements while emulating deterministic thread-head queries."""

    def __init__(self, items: list[Email] | None = None) -> None:
        """Initialize captured queries and source email rows."""
        self.items = list(items or [])
        self.queries: list[object] = []

    async def execute(self, query, params=None):
        """Record one statement and emulate the ranked-head or message result."""
        del params
        self.queries.append(query)
        query_text = str(query).lower()
        ordered_items = sorted(
            self.items,
            key=lambda email: (email.date, email.id or 0),
            reverse=True,
        )
        if "ranked_thread_heads" not in query_text:
            return _ScalarsResult(ordered_items)

        heads_by_thread: dict[str, Email] = {}
        for email in ordered_items:
            heads_by_thread.setdefault(emails_api.canonical_thread_key(email), email)
        heads = list(heads_by_thread.values())
        limit_clause = getattr(query, "_limit_clause", None)
        limit_value = getattr(limit_clause, "value", None)
        if limit_value is not None:
            heads = heads[:limit_value]
        return _ScalarsResult(heads)


def _sent_email(message_id: str, email_id: int, thread_id: str = "thread_1") -> Email:
    """Build one equal-date sent message with a deterministic database id."""
    return Email(
        id=email_id,
        user_id="user_1",
        organization_id="org_1",
        message_id=message_id,
        thread_id=thread_id,
        sender="me@example.com",
        recipients="client@example.com",
        subject="Reply ordering",
        date=EQUAL_DATE,
        body="Please reply.",
    )


def _external_email(message_id: str, email_id: int) -> Email:
    """Build one equal-date external reply with a deterministic database id."""
    return Email(
        id=email_id,
        user_id="user_1",
        organization_id="org_1",
        message_id=message_id,
        thread_id="thread_1",
        sender="client@example.com",
        recipients="me@example.com",
        subject="Reply ordering",
        date=EQUAL_DATE,
        body="Crossed in transit.",
    )


@pytest.mark.asyncio
async def test_get_emails_orders_ranked_heads_by_date_then_id(monkeypatch) -> None:
    """Equal-date thread heads must page deterministically by database id."""

    async def _tenant_config(_db, _user_id, _organization_id):
        return None

    monkeypatch.setattr(emails_api, "get_scoped_tenant_config", _tenant_config)
    lower_head = _sent_email("lower-head", 1, "thread-low")
    higher_head = _sent_email("higher-head", 2, "thread-high")
    session = _QueryCapturingSession([lower_head, higher_head])

    response = await emails_api.get_emails(
        limit=1,
        folder="inbox",
        db=session,
        auth_context=SimpleNamespace(user_id="user_1", organization_id="org_1"),
    )

    assert [item.id for item in response["emails"]] == [higher_head.id]
    assert len(session.queries) == 2
    head_query_text = str(session.queries[0]).lower()
    tie_break_order = "order by email_records.date desc, email_records.id desc"
    assert head_query_text.count(tie_break_order) >= 2


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
    assert (
        thread_requires_reply(
            [higher_id, lower_id],
            USER_ADDRESSES,
            is_descending=True,
        )
        is True
    )


def test_equal_date_higher_id_external_message_suppresses_sent_candidate() -> None:
    """Database id must break equal-date ties in favor of the later external row."""
    sent_message = _sent_email("sent-low", 1)
    external_reply = _external_email("external-high", 2)

    assert thread_reply_candidate(
        [sent_message, external_reply],
        USER_ADDRESSES,
    ) is None
    assert thread_reply_candidate(
        [external_reply, sent_message],
        USER_ADDRESSES,
        is_descending=True,
    ) is None
    assert (
        thread_requires_reply(
            [external_reply, sent_message],
            USER_ADDRESSES,
            is_descending=True,
        )
        is False
    )


def test_equal_date_higher_id_sent_message_remains_reply_candidate() -> None:
    """A later sent row must not be suppressed by an earlier equal-date reply."""
    external_message = _external_email("external-low", 1)
    sent_message = _sent_email("sent-high", 2)

    assert thread_reply_candidate(
        [external_message, sent_message],
        USER_ADDRESSES,
    ) is sent_message
    assert thread_reply_candidate(
        [sent_message, external_message],
        USER_ADDRESSES,
        is_descending=True,
    ) is sent_message
    assert (
        thread_requires_reply(
            [sent_message, external_message],
            USER_ADDRESSES,
            is_descending=True,
        )
        is True
    )
