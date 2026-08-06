from db.models import Email
from services.reply_sla_escalation_service import canonical_reply_sla_thread_key

def test_canonical_reply_sla_thread_key():
    # Test with thread_id present and normalized (trims <> and spaces)
    email1 = Email(thread_id="<thread 1@example.com>", message_id="<msg1@example.com>")
    assert canonical_reply_sla_thread_key(email1) == "thread1@example.com"

    # Test with thread_id present but missing brackets
    email2 = Email(thread_id="thread2@example.com", message_id="<msg2@example.com>")
    assert canonical_reply_sla_thread_key(email2) == "thread2@example.com"

    # Test with no thread_id, falls back to message_id (normalized)
    email3 = Email(thread_id=None, message_id="<msg3@example.com>")
    assert canonical_reply_sla_thread_key(email3) == "msg3@example.com"

    # Test with no thread_id and message_id missing brackets
    email4 = Email(thread_id=None, message_id="msg4@example.com")
    assert canonical_reply_sla_thread_key(email4) == "msg4@example.com"

    # Test fallback to raw message_id if both normalization fails
    email5 = Email(thread_id="   ", message_id="   ")
    assert canonical_reply_sla_thread_key(email5) == "   "
