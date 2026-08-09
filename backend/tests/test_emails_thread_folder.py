from db.models import Email
from api.emails import thread_matches_folder

def test_thread_matches_folder_inbox():
    # It should return True for inbox folder regardless of messages
    assert thread_matches_folder([], set(), "inbox")

def test_thread_matches_folder_sent_no_messages():
    # If there are no messages, it should return False for sent folder
    assert not thread_matches_folder([], set(), "sent")

def test_thread_matches_folder_sent_with_matching_message():
    # Create mock email messages
    user_addresses = {"user@example.com"}
    matching_message = Email(
        id="1",
        message_id="m1",
        thread_id="t1",
        subject="test",
        sender="user@example.com",
        recipients="other@example.com",
        date="2023-01-01T00:00:00Z"
    )
    non_matching_message = Email(
        id="2",
        message_id="m2",
        thread_id="t1",
        subject="test 2",
        sender="other@example.com",
        recipients="user@example.com",
        date="2023-01-01T00:00:00Z"
    )

    # Should match because one message is from the user
    assert thread_matches_folder([non_matching_message, matching_message], user_addresses, "sent")

def test_thread_matches_folder_sent_without_matching_message():
    user_addresses = {"user@example.com"}
    non_matching_message1 = Email(
        id="1",
        message_id="m1",
        thread_id="t1",
        subject="test",
        sender="other@example.com",
        recipients="user@example.com",
        date="2023-01-01T00:00:00Z"
    )
    non_matching_message2 = Email(
        id="2",
        message_id="m2",
        thread_id="t1",
        subject="test 2",
        sender="another@example.com",
        recipients="user@example.com",
        date="2023-01-01T00:00:00Z"
    )

    # Should not match because no message is from the user
    assert not thread_matches_folder([non_matching_message1, non_matching_message2], user_addresses, "sent")
