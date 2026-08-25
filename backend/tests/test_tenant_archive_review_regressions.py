"""Review regressions for tenant archive deduplication and task relinking."""

from __future__ import annotations

from typing import Any

import pytest

from db.models import Email, TicketTask
from services.tenant_archive_service import (
    ARCHIVE_KIND,
    CURRENT_ARCHIVE_SCHEMA_VERSION,
    _find_existing_email,
    import_tenant_archive,
)


class _Scalars:
    """Minimal SQLAlchemy scalar-result facade."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Result:
    """Minimal result facade for focused archive-service tests."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)

    def scalar_one_or_none(self):
        if not self._rows:
            return None
        if len(self._rows) != 1:
            raise AssertionError("Expected at most one result row")
        return self._rows[0]


class _StatementCaptureSession:
    """Capture the query issued by the email duplicate lookup."""

    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result([])


@pytest.mark.asyncio
async def test_email_fingerprint_is_a_fallback_not_an_additional_requirement():
    """Message-id and fingerprint duplicate identities must be alternatives."""
    session = _StatementCaptureSession()

    await _find_existing_email(
        session,
        owner_user_id="alice",
        organization_id="org-acme",
        message_id="new-message@example.com",
        fingerprint="stable-fingerprint",
    )

    assert session.statement is not None
    sql = str(
        session.statement.compile(
            compile_kwargs={"literal_binds": True},
        )
    ).upper()
    assert " OR " in sql, sql


class _ExistingDestinationSession:
    """Destination session with one pre-existing email and no tasks."""

    def __init__(self) -> None:
        self.existing_email = Email(
            id=41,
            user_id="alice",
            organization_id="org-acme",
            message_id="<already-there@example.com>",
            fingerprint="existing-fingerprint",
            sender="sender@example.com",
            recipients="alice@example.com",
            subject="Existing destination mail",
            body="Existing",
            is_read=True,
        )
        self.tasks: list[TicketTask] = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0]["entity"] if descriptions else None
        if entity is Email:
            return _Result([self.existing_email])
        if entity is TicketTask:
            return _Result([])
        return _Result([])

    def add_all(self, objects) -> None:
        for obj in objects:
            if isinstance(obj, TicketTask):
                self.tasks.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def _task_only_bundle() -> dict[str, Any]:
    """Return a valid partial bundle whose email already exists at destination."""
    return {
        "manifest": {
            "archive_kind": ARCHIVE_KIND,
            "schema_version": CURRENT_ARCHIVE_SCHEMA_VERSION,
            "source_scope": {
                "owner_user_id": "alice",
                "organization_id": "org-acme",
            },
        },
        "records": {
            "emails": [],
            "ticket_tasks": [
                {
                    "task_uid": "taskuidpartialbundle000000000001",
                    "title": "Follow up on existing mail",
                    "status": "open",
                    "priority": "normal",
                    "source_type": "email",
                    "related_message_id": "<already-there@example.com>",
                    "related_thread_id": "<existing-thread>",
                    "created_at": "2026-08-25T07:00:00+00:00",
                    "updated_at": "2026-08-25T07:00:00+00:00",
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_partial_bundle_task_relinks_to_existing_destination_email():
    """A task-only bundle must preserve a link found in the destination scope."""
    session = _ExistingDestinationSession()

    summary = await import_tenant_archive(
        session,
        bundle=_task_only_bundle(),
        owner_user_id="alice",
        organization_id="org-acme",
    )

    assert summary["ticket_tasks"]["imported"] == 1
    assert len(session.tasks) == 1
    assert session.tasks[0].related_email_id == session.existing_email.id
