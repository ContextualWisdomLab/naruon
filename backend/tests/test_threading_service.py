import pytest

from services.threading_service import assign_thread_id


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
async def test_multi_id_in_reply_to_threads_on_first_parent_message_id():
    """A multi message-id In-Reply-To must join the first parent's thread.

    RFC 5322 §3.6.4 defines ``in-reply-to = "In-Reply-To:" 1*msg-id`` — the
    field may legitimately carry more than one message-id. jwz's "message
    threading" says to extract the first message-id-looking token from
    In-Reply-To. The immediate parent identifier must therefore be that first
    id (``<parent@example.com>``), not the raw concatenation of both ids, so the
    reply threads onto the already-imported parent.
    """
    session = _SequentialSession([[("<parent@example.com>", "thread-123")]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com> <cc-parent@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-123"


@pytest.mark.asyncio
async def test_multi_id_in_reply_to_deterministic_root_is_first_message_id():
    """A multi message-id In-Reply-To yields the first id as the thread root.

    Per RFC 5322 §3.6.4 In-Reply-To is ``1*msg-id``; when References is absent
    and the parent has not been imported yet, the deterministic thread root must
    be the first parsed message-id (jwz: use the first message-id from
    In-Reply-To), never the mangled ``"parent@example.com> <cc-parent@…"``
    string produced by stripping angle brackets off the whole header.
    """
    session = _SequentialSession([[]])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com> <cc-parent@example.com>",
            "references": None,
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "parent@example.com"


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
