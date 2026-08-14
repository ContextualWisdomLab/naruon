from api import emails as emails_api
from db.models import Email


def test_canonical_thread_key_prefers_thread_id_and_normalizes_headers() -> None:
    assert (
        emails_api.canonical_thread_key(
            Email(thread_id="<thread1@domain.com>", message_id="<msg1@domain.com>")
        )
        == "thread1@domain.com"
    )
    assert (
        emails_api.canonical_thread_key(
            Email(thread_id=None, message_id="<msg2@domain.com>")
        )
        == "msg2@domain.com"
    )
    assert (
        emails_api.canonical_thread_key(Email(thread_id="thread3", message_id="msg3"))
        == "thread3"
    )
    assert (
        emails_api.canonical_thread_key(
            Email(thread_id="<thread 2@domain.com>", message_id="")
        )
        == "thread2@domain.com"
    )


def test_thread_lookup_values_cover_canonical_and_persisted_forms() -> None:
    assert set(emails_api.thread_lookup_values("<thread1@domain.com>")) == {
        "<thread1@domain.com>",
        "thread1@domain.com",
    }
    assert set(emails_api.thread_lookup_values("thread2")) == {
        "thread2",
        "<thread2>",
    }
    assert set(emails_api.thread_lookup_values("<thread 3@domain.com>")) == {
        "<thread 3@domain.com>",
        "thread3@domain.com",
        "<thread3@domain.com>",
    }
