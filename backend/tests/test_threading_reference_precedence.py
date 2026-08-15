"""Regression tests for standards-defined email thread ancestry precedence."""

import pytest

from services.threading_service import assign_thread_id


class _Result:
    """Minimal SQLAlchemy-like result for deterministic threading tests."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    """Minimal async session returning the configured message/thread rows."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _query):
        return _Result(self._rows)


@pytest.mark.asyncio
async def test_references_header_precedes_conflicting_in_reply_to_thread():
    """A valid References chain is authoritative for REFERENCES threading.

    RFC 5256 defines the References header as the ancestry source whenever it
    contains valid Message-IDs; In-Reply-To is only the fallback when References
    is absent or has no valid Message-ID. A conflicting parent must therefore
    not pull this message into a different already-imported thread.
    """
    session = _Session(
        [
            ("<parent@example.com>", "thread-parent"),
            ("<root@example.com>", "thread-root"),
        ]
    )

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": "<root@example.com>",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "thread-root"


@pytest.mark.asyncio
async def test_references_header_does_not_fall_back_to_existing_in_reply_to_thread():
    """Valid References remain authoritative even when only the parent exists.

    When the referenced ancestor has not been imported yet, using an unrelated
    existing In-Reply-To row would make arrival order change thread identity.
    The deterministic fallback must remain the oldest valid References ID.
    """
    session = _Session([("<parent@example.com>", "thread-parent")])

    thread_id = await assign_thread_id(
        session,
        {
            "message_id": "<reply@example.com>",
            "in_reply_to": "<parent@example.com>",
            "references": "<root@example.com>",
        },
        user_id="testuser",
        organization_id="org-acme",
    )

    assert thread_id == "root@example.com"
