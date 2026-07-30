import pytest

from services.threading_service import (
    assign_thread_id,
    extract_reference_ids,
    normalize_message_id,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _SequentialSession:
    def __init__(self, values):
        self._values = list(values)
        self.execute_count = 0

    async def execute(self, _query):
        self.execute_count += 1
        rows = self._values.pop(0) if self._values else []
        return _Result(rows)


class _QueryCapturingSession(_SequentialSession):
    def __init__(self, values):
        super().__init__(values)
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return await super().execute(query)


@pytest.mark.asyncio
async def test_reply_before_root_uses_first_reference_as_deterministic_thread_id():
    session = _SequentialSession([[]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": "<root@example.com> <parent@example.com>",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "root@example.com"


@pytest.mark.asyncio
async def test_reply_without_references_uses_in_reply_to_as_deterministic_thread_id():
    session = _SequentialSession([[]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "parent@example.com"


@pytest.mark.asyncio
async def test_existing_parent_thread_id_wins_over_deterministic_fallback():
    session = _SequentialSession([[("<parent@example.com>", "thread-123")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": "<root@example.com> <parent@example.com>",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-123"


@pytest.mark.asyncio
async def test_existing_legacy_bracketed_thread_id_is_normalized():
    session = _SequentialSession([[("<root@example.com>", "<root@example.com>")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<root@example.com>",
            "references": "<root@example.com>",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "root@example.com"


@pytest.mark.asyncio
async def test_forwarded_subject_alone_does_not_merge_unrelated_thread():
    session = _SequentialSession([[("unrelated@example.com", "unrelated-thread")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<forwarded-copy@example.com>",
            "in_reply_to": None,
            "references": None,
            "subject": "Fwd: Q2 출시 계획",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "forwarded-copy@example.com"
    assert session.execute_count == 0


@pytest.mark.asyncio
async def test_existing_thread_lookup_is_scoped_to_owner_and_organization():
    session = _QueryCapturingSession([[("<parent@example.com>", "thread-123")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-123"
    query_text = str(session.queries[-1]).lower()
    assert "email_records.user_id" in query_text
    assert "email_records.organization_id" in query_text


def test_normalize_message_id_strips_brackets_and_outer_whitespace():
    assert normalize_message_id("<abc@example.com>") == "abc@example.com"
    assert normalize_message_id("  <abc@example.com>  ") == "abc@example.com"
    assert normalize_message_id("< abc@example.com >") == "abc@example.com"
    assert normalize_message_id("<<abc@example.com>>") == "abc@example.com"
    assert normalize_message_id("abc@example.com") == "abc@example.com"


def test_normalize_message_id_handles_empty_and_none():
    assert normalize_message_id(None) is None
    assert normalize_message_id("") is None
    assert normalize_message_id("   ") is None
    assert normalize_message_id("<>") is None


def test_normalize_message_id_collapses_interior_unfolding_whitespace():
    # RFC 5322 section 2.2.3 header unfolding can leave interior whitespace when
    # a folded Message-ID is rejoined; RFC 5322 section 3.6.4 msg-id carries
    # none, so the folded and unfolded forms must normalize to the same value or
    # dedup/threading would treat one message as two.
    canonical = normalize_message_id("<abc@example.com>")
    assert normalize_message_id("<abc@ example.com>") == canonical
    assert normalize_message_id("<abc @example.com>") == canonical
    assert normalize_message_id("<abc@\r\n example.com>") == canonical
    assert normalize_message_id("<abc@\texample.com>") == canonical


def test_extract_reference_ids_normalizes_folded_whitespace_and_dedupes():
    header = "<a@x.com> <a@ x.com>\r\n <b@x.com>"
    # The first two are the same id split over a fold boundary, so only two
    # distinct references remain, in header order.
    assert extract_reference_ids(header) == ["a@x.com", "b@x.com"]


@pytest.mark.asyncio
async def test_multi_id_in_reply_to_threads_on_any_existing_parent():
    # RFC 5322 section 3.6.4: In-Reply-To is 1*msg-id, so it may carry more than
    # one parent id (a reply that joins two messages). Threading must consider
    # every parent, not treat the whole header as one opaque id -- otherwise a
    # multi-id In-Reply-To never matches an existing thread and the reply splits
    # off on its own.
    session = _SequentialSession([[("<older@example.com>", "thread-xyz")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<newer@example.com> <older@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-xyz"


@pytest.mark.asyncio
async def test_multi_id_in_reply_to_fallback_uses_first_parent_as_root():
    session = _SequentialSession([[]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<first@example.com> <second@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "first@example.com"


@pytest.mark.asyncio
async def test_in_reply_to_with_cfws_comment_extracts_bare_msg_id():
    # RFC 5322 sections 3.6.4 / 3.2.2 permit CFWS (e.g. a trailing comment) around
    # a msg-id. The comment text must not leak into the id, or the reply is
    # threaded/deduped against a garbage id and splits from its parent thread.
    session = _SequentialSession([[("<parent@example.com>", "thread-123")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com> (sent from my phone)",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-123"
