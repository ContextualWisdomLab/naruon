import datetime

from db.models import Email
from services.reply_tracking_service import (
    detect_reply_tracking,
    thread_reply_candidate,
)


USER_ADDRESSES = {"me@example.com"}
BASE_TIME = datetime.datetime(2026, 5, 28, 9, 0, tzinfo=datetime.timezone.utc)


def make_email(
    message_id: str,
    *,
    sender: str,
    recipients: str,
    minutes: int,
    body: str = "Could you please reply?",
) -> Email:
    return Email(
        user_id="user_1",
        organization_id="org_1",
        message_id=message_id,
        thread_id="thread_1",
        sender=sender,
        recipients=recipients,
        subject="Reply tracking",
        date=BASE_TIME + datetime.timedelta(minutes=minutes),
        body=body,
    )


def test_thread_reply_candidate_returns_latest_unanswered_sent_message():
    older_sent = make_email(
        "sent_older",
        sender="Me <me@example.com>",
        recipients="client@example.com",
        minutes=0,
    )
    external_reply = make_email(
        "external_reply",
        sender="client@example.com",
        recipients="me@example.com",
        minutes=5,
        body="Thanks, received.",
    )
    latest_sent = make_email(
        "sent_latest",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=10,
    )

    candidate = thread_reply_candidate(
        [latest_sent, older_sent, external_reply],
        USER_ADDRESSES,
    )

    assert candidate is latest_sent


def test_thread_reply_candidate_ignores_sent_message_with_later_external_reply():
    sent_message = make_email(
        "sent_needs_reply",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    later_external_reply = make_email(
        "external_later",
        sender="client@example.com",
        recipients="me@example.com",
        minutes=1,
        body="I will handle it.",
    )

    assert (
        thread_reply_candidate([sent_message, later_external_reply], USER_ADDRESSES)
        is None
    )


def test_thread_reply_candidate_ignores_self_sent_knowledge_messages():
    self_sent = make_email(
        "self_sent",
        sender="Me <me@example.com>",
        recipients="me@example.com",
        minutes=0,
    )

    assert thread_reply_candidate([self_sent], USER_ADDRESSES) is None


def test_thread_reply_candidate_keeps_mixed_recipient_message():
    sent = make_email(
        "self_and_client",
        sender="me@example.com",
        recipients="me@example.com, client@example.com",
        minutes=0,
    )

    assert thread_reply_candidate([sent], USER_ADDRESSES) is sent


def test_thread_reply_candidate_preserves_strict_later_reply_boundary():
    sent_message = make_email(
        "sent_same_time",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    same_time_external = make_email(
        "external_same_time",
        sender="client@example.com",
        recipients="me@example.com",
        minutes=0,
        body="Crossed in transit.",
    )

    candidate = thread_reply_candidate(
        [same_time_external, sent_message],
        USER_ADDRESSES,
    )

    assert candidate is sent_message


def test_configured_email_addresses_handles_none():
    from services.reply_tracking_service import configured_email_addresses

    assert configured_email_addresses(None) == set()


def test_configured_email_addresses_includes_pop3_alias():
    from db.models import TenantConfig
    from services.reply_tracking_service import configured_email_addresses

    config = TenantConfig(
        user_id="owner",
        smtp_username="sent@example.com",
        imap_username="inbox@example.com",
        pop3_username="archive@example.com",
    )

    assert configured_email_addresses(config) == {
        "sent@example.com",
        "inbox@example.com",
        "archive@example.com",
    }


def test_thread_reply_candidate_returns_none_when_no_user_addresses():
    sent_message = make_email(
        "sent_needs_reply",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    assert thread_reply_candidate([sent_message], set()) is None


def test_thread_requires_reply_returns_true_when_candidate_exists():
    from services.reply_tracking_service import thread_requires_reply

    sent_message = make_email(
        "sent_needs_reply",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    assert thread_requires_reply([sent_message], USER_ADDRESSES) is True


def test_thread_requires_reply_returns_false_when_no_candidate():
    from services.reply_tracking_service import thread_requires_reply

    sent_message = make_email(
        "sent_needs_reply",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    later_external_reply = make_email(
        "external_later",
        sender="client@example.com",
        recipients="me@example.com",
        minutes=1,
        body="I will handle it.",
    )
    assert (
        thread_requires_reply([sent_message, later_external_reply], USER_ADDRESSES)
        is False
    )


def test_thread_reply_candidate_tie_order_consistent_across_modes():
    sent_a = make_email(
        "sent_a",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    sent_a.id = 1
    sent_b = make_email(
        "sent_b",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=0,
    )
    sent_b.id = 2

    candidate_sorted = thread_reply_candidate(
        [sent_a, sent_b], USER_ADDRESSES, is_chronological=False
    )
    candidate_reversed = thread_reply_candidate(
        [sent_a, sent_b], USER_ADDRESSES, is_chronological=True
    )

    assert candidate_sorted is candidate_reversed

def test_detect_reply_tracking_please_reply():
    assert (
        detect_reply_tracking("This is an important message, please reply soon.")
        is True
    )

def test_detect_reply_tracking_question_mark():
    assert detect_reply_tracking("How are you doing today?") is True

def test_detect_reply_tracking_case_insensitive():
    assert detect_reply_tracking("Please Reply to this email.") is True

def test_detect_reply_tracking_no_match():
    assert detect_reply_tracking(
        "This is a standard statement without any tracking triggers."
    ) is False

def test_detect_reply_tracking_empty_body():
    assert detect_reply_tracking(None) is False
    assert detect_reply_tracking("") is False


def test_thread_reply_candidate_is_chronological_optimization():
    older_sent = make_email(
        "sent_older",
        sender="Me <me@example.com>",
        recipients="client@example.com",
        minutes=60,
        body="Any update?",
    )
    external_reply = make_email(
        "reply",
        sender="client@example.com",
        recipients="Me <me@example.com>",
        minutes=30,
        body="Yes, here it is.",
    )
    latest_sent = make_email(
        "sent_latest",
        sender="me@example.com",
        recipients="client@example.com",
        minutes=10,
        body="please reply",
    )

    candidate = thread_reply_candidate(
        [latest_sent, external_reply, older_sent],
        USER_ADDRESSES,
        is_chronological=True,
    )

    assert candidate is older_sent
