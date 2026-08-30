"""Focused regression coverage for email thread identity and folder visibility."""

from types import SimpleNamespace

from api.emails import canonical_thread_key, thread_lookup_values, thread_matches_folder


def _message(*, thread_id: str | None = None, message_id: str = "", sender: str = ""):
    """Build the minimal message shape consumed by thread helper contracts."""
    return SimpleNamespace(thread_id=thread_id, message_id=message_id, sender=sender)


def test_canonical_thread_key_prefers_normalized_thread_id():
    """Use the normalized thread identifier before falling back to Message-ID."""
    assert (
        canonical_thread_key(
            _message(thread_id="<thread1@domain.com>", message_id="<msg1@domain.com>")
        )
        == "thread1@domain.com"
    )
    assert (
        canonical_thread_key(_message(thread_id="thread3", message_id="msg3"))
        == "thread3"
    )
    assert (
        canonical_thread_key(
            _message(thread_id="<thread 2@domain.com>", message_id="")
        )
        == "thread2@domain.com"
    )


def test_canonical_thread_key_falls_back_to_normalized_message_id():
    """Use Message-ID when a usable thread identifier is absent."""
    assert (
        canonical_thread_key(_message(thread_id=None, message_id="<msg2@domain.com>"))
        == "msg2@domain.com"
    )
    assert (
        canonical_thread_key(_message(thread_id="", message_id="<msg1@domain.com>"))
        == "msg1@domain.com"
    )


def test_thread_lookup_values_include_persisted_canonical_and_bracketed_forms():
    """Expand lookup values without losing the originally persisted spelling."""
    assert set(thread_lookup_values("<thread1@domain.com>")) == {
        "<thread1@domain.com>",
        "thread1@domain.com",
    }
    assert set(thread_lookup_values("thread2")) == {"thread2", "<thread2>"}
    assert set(thread_lookup_values("<thread 3@domain.com>")) == {
        "<thread 3@domain.com>",
        "thread3@domain.com",
        "<thread3@domain.com>",
    }


def test_thread_matches_folder_inbox_is_visible_without_messages():
    """Inbox thread visibility is independent of whether a sender matches the user."""
    assert thread_matches_folder([], set(), "inbox") is True


def test_thread_matches_folder_sent_requires_a_user_sender():
    """Sent-folder visibility requires at least one message from a configured address."""
    user_addresses = {"user@example.com"}
    external = _message(sender="Other Person <other@example.com>")
    user_message = _message(sender="User Name <USER@example.com>")

    assert thread_matches_folder([], user_addresses, "sent") is False
    assert thread_matches_folder([external], user_addresses, "sent") is False
    assert thread_matches_folder([external, user_message], user_addresses, "sent") is True
