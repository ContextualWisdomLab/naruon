"""Unit tests for tenant archive export/import services.

These tests exercise ``services.tenant_archive_service`` against an in-memory
mock ``AsyncSession`` following the repo's mocked-session conventions (see
``tests/test_tasks_api.py``). They cover:

- deterministic, versioned manifest construction;
- owner + organization scoping of exported records;
- attachment reference listing without binary content or embeddings;
- import that preserves opaque public ids and source provenance;
- idempotent re-import (dedupe-safe, all-skipped second pass);
- fail-closed validation with deterministic error codes.
"""

import datetime

import pytest

from db.models import Attachment, Email, TicketTask
from services.tenant_archive_service import (
    ARCHIVE_KIND,
    CURRENT_ARCHIVE_SCHEMA_VERSION,
    SUPPORTED_ARCHIVE_SCHEMA_VERSIONS,
    TenantArchiveBundleInvalid,
    TenantArchiveSchemaUnsupported,
    TenantArchiveScopeMismatch,
    export_tenant_archive,
    import_tenant_archive,
)

UTC = datetime.timezone.utc


class _MockScalars:
    """Minimal scalars() facade over a list of ORM rows."""

    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class _MockResult:
    """Minimal execute() result facade used by the mock session."""

    def __init__(self, items: list) -> None:
        self._items = items

    def scalars(self) -> _MockScalars:
        return _MockScalars(self._items)

    def scalar_one_or_none(self):
        if not self._items:
            return None
        if len(self._items) > 1:
            raise AssertionError("Mock result expected at most one row")
        return self._items[0]


def _param(params: dict, name: str):
    """Extract a compiled bind param value by its base name suffix."""
    value = params.get(f"{name}_1")
    return value


def _as_set(value) -> set:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return set(value)
    return {value}


class MockArchiveSession:
    """In-memory AsyncSession double for archive service unit tests."""

    def __init__(self) -> None:
        self.emails: list[Email] = []
        self.tasks: list[TicketTask] = []
        self.commit_count = 0
        self.rollback_count = 0
        self._next_email_id = 1
        self._next_task_id = 1

    async def execute(self, stmt):
        descriptions = getattr(stmt, "column_descriptions", [])
        entity = descriptions[0]["entity"] if descriptions else None
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        if entity is Email:
            user_id = _param(params, "user_id")
            organization_id = _param(params, "organization_id")
            message_ids = _as_set(_param(params, "message_id"))
            fingerprint = _param(params, "fingerprint")
            selected = []
            for email in self.emails:
                if user_id is not None and email.user_id != user_id:
                    continue
                if organization_id is not None and (
                    email.organization_id != organization_id
                ):
                    continue
                matches_message = bool(message_ids) and (
                    email.message_id in message_ids
                )
                matches_fingerprint = fingerprint is not None and (
                    email.fingerprint == fingerprint
                )
                if message_ids and not fingerprint:
                    if not matches_message:
                        continue
                elif fingerprint and not message_ids:
                    if not matches_fingerprint:
                        continue
                elif message_ids and fingerprint:
                    if not (matches_message or matches_fingerprint):
                        continue
                selected.append(email)
            return _MockResult(selected)
        if entity is TicketTask:
            task_uid = _param(params, "task_uid")
            user_id = _param(params, "user_id")
            organization_id = _param(params, "organization_id")
            selected = [
                task
                for task in self.tasks
                if (task_uid is None or task.task_uid == task_uid)
                and (user_id is None or task.user_id == user_id)
                and (
                    organization_id is None
                    or task.organization_id == organization_id
                )
            ]
            return _MockResult(selected)
        return _MockResult([])

    def add_all(self, objs) -> None:
        for obj in objs:
            if isinstance(obj, Email):
                self.emails.append(obj)
            elif isinstance(obj, TicketTask):
                self.tasks.append(obj)
            else:  # pragma: no cover - defensive
                raise AssertionError(f"Unexpected object staged: {type(obj)!r}")

    async def flush(self) -> None:
        for email in self.emails:
            if email.id is None:
                email.id = self._next_email_id
                self._next_email_id += 1
        for task in self.tasks:
            if task.id is None:
                task.id = self._next_task_id
                self._next_task_id += 1

    async def commit(self) -> None:
        await self.flush()
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1

    def wipe_owner_scope(self, *, user_id: str, organization_id: str) -> None:
        """Simulate wiping the destination scope before a clean import."""
        self.emails = [
            email
            for email in self.emails
            if not (
                email.user_id == user_id
                and email.organization_id == organization_id
            )
        ]
        self.tasks = [
            task
            for task in self.tasks
            if not (
                task.user_id == user_id
                and task.organization_id == organization_id
            )
        ]


def make_email(
    *,
    message_id: str,
    subject: str = "Hello",
    body: str = "Body text",
    date: datetime.datetime | None = None,
    thread_id: str | None = None,
    fingerprint: str | None = "fp-1",
    sender: str = "sender@example.com",
    recipients: str = "owner@example.com",
    attachments: tuple[dict, ...] = (),
) -> Email:
    """Build an Email row fixture without touching vector payloads."""
    email = Email(
        user_id="alice",
        organization_id="org-acme",
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=fingerprint,
        sender=sender,
        recipients=recipients,
        subject=subject,
        date=date or datetime.datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
        body=body,
        is_read=False,
    )
    for spec in attachments:
        email.attachments.append(
            Attachment(
                filename=spec["filename"],
                content=spec.get("content", ""),
                content_type=spec.get("content_type", "text/plain"),
                parse_status=spec.get("parse_status", "parsed"),
                parse_content_type=spec.get("parse_content_type", "text/plain"),
                parser_key=spec.get("parser_key", "plain_text"),
                parse_error_code=spec.get("parse_error_code"),
            )
        )
    return email


def make_task(
    *,
    task_uid: str = "taskuid000000000000000000000001",
    title: str = "Follow up",
    status: str = "open",
    priority: str = "normal",
    source_type: str = "email",
    related_email: Email | None = None,
    related_thread_id: str | None = None,
    created_at: datetime.datetime | None = None,
) -> TicketTask:
    """Build a TicketTask row fixture."""
    moment = created_at or datetime.datetime(2026, 7, 11, 8, 30, tzinfo=UTC)
    return TicketTask(
        task_uid=task_uid,
        user_id="alice",
        organization_id="org-acme",
        title=title,
        status=status,
        priority=priority,
        source_type=source_type,
        related_email_id=related_email.id if related_email else None,
        related_thread_id=(
            related_thread_id
            if related_thread_id is not None
            else (related_email.thread_id if related_email else None)
        ),
        created_at=moment,
        updated_at=moment,
    )


@pytest.fixture
def seeded_session() -> MockArchiveSession:
    """Two scoped emails (one threaded pair), one attachment, two tasks."""
    session = MockArchiveSession()
    older = make_email(
        message_id="<old@example.com>",
        thread_id="<thread-a>",
        subject="Older mail",
        date=datetime.datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        attachments=(
            {"filename": "report.txt", "content_type": "text/plain"},
        ),
    )
    newer = make_email(
        message_id="<new@example.com>",
        thread_id="<thread-a>",
        subject="Newer reply",
        date=datetime.datetime(2026, 7, 2, 9, 0, tzinfo=UTC),
    )
    session.emails.extend([older, newer])
    for email in session.emails:
        email.id = session._next_email_id
        session._next_email_id += 1
    session.tasks.extend(
        [
            make_task(
                task_uid="taskuidaaaaaaaaaaaaaaaaaaaaaaaa01",
                related_email=newer,
                created_at=datetime.datetime(2026, 7, 3, 8, 0, tzinfo=UTC),
            ),
            make_task(
                task_uid="taskuidbbbbbbbbbbbbbbbbbbbbbbbb02",
                title="Standalone note",
                related_email=None,
                related_thread_id=None,
                source_type="manual",
                created_at=datetime.datetime(2026, 7, 2, 8, 0, tzinfo=UTC),
            ),
        ]
    )
    for task in session.tasks:
        task.id = session._next_task_id
        session._next_task_id += 1
    return session


@pytest.mark.asyncio
async def test_export_builds_versioned_manifest_and_records(seeded_session):
    bundle = await export_tenant_archive(
        seeded_session, owner_user_id="alice", organization_id="org-acme"
    )

    manifest = bundle["manifest"]
    assert manifest["archive_kind"] == ARCHIVE_KIND
    assert manifest["schema_version"] == CURRENT_ARCHIVE_SCHEMA_VERSION
    assert manifest["schema_version"] in SUPPORTED_ARCHIVE_SCHEMA_VERSIONS
    assert manifest["source_scope"]["owner_user_id"] == "alice"
    assert manifest["source_scope"]["organization_id"] == "org-acme"
    assert manifest["counts"]["emails"] == 2
    assert manifest["counts"]["ticket_tasks"] == 2
    assert manifest["counts"]["attachment_references"] == 1
    assert "credentials" in manifest["excluded_domains"]
    records = bundle["records"]
    assert [record["message_id"] for record in records["emails"]] == [
        "<old@example.com>",
        "<new@example.com>",
    ]
    assert [record["task_uid"] for record in records["ticket_tasks"]] == [
        "taskuidbbbbbbbbbbbbbbbbbbbbbbbb02",
        "taskuidaaaaaaaaaaaaaaaaaaaaaaaa01",
    ]
    task_record = next(
        record
        for record in records["ticket_tasks"]
        if record["related_message_id"] == "<new@example.com>"
    )
    assert task_record["related_thread_id"] == "<thread-a>"
    assert task_record["title"] == "Follow up"


@pytest.mark.asyncio
async def test_export_scopes_records_to_session_owner(seeded_session):
    outsider_email = make_email(message_id="<outsider@example.com>")
    outsider_email.user_id = "mallory"
    seeded_session.emails.append(outsider_email)
    outsider_task = make_task(task_uid="taskuidcccccccccccccccccccccccc03")
    outsider_task.user_id = "mallory"
    seeded_session.tasks.append(outsider_task)

    bundle = await export_tenant_archive(
        seeded_session, owner_user_id="alice", organization_id="org-acme"
    )

    exported_ids = {
        record["message_id"] for record in bundle["records"]["emails"]
    }
    assert "<outsider@example.com>" not in exported_ids
    exported_uids = {
        record["task_uid"] for record in bundle["records"]["ticket_tasks"]
    }
    assert "taskuidcccccccccccccccccccccccc03" not in exported_uids


@pytest.mark.asyncio
async def test_export_lists_attachment_references_without_binary_payloads(
    seeded_session,
):
    bundle = await export_tenant_archive(
        seeded_session, owner_user_id="alice", organization_id="org-acme"
    )

    old_record = bundle["records"]["emails"][0]
    assert old_record["attachments"] == [
        {
            "attachment_ref": "<old@example.com>#attachment-1",
            "filename": "report.txt",
            "content_type": "text/plain",
            "parse_status": "parsed",
            "parse_content_type": "text/plain",
            "parser_key": "plain_text",
            "parse_error_code": None,
        }
    ]
    records_blob = repr(bundle["records"])
    assert "embedding" not in records_blob.lower()
    new_record = bundle["records"]["emails"][1]
    assert new_record["attachments"] == []


@pytest.mark.asyncio
async def test_import_into_clean_scope_preserves_opaque_ids_and_provenance(
    seeded_session,
):
    bundle = await export_tenant_archive(
        seeded_session, owner_user_id="alice", organization_id="org-acme"
    )

    destination = MockArchiveSession()
    summary = await import_tenant_archive(
        destination,
        bundle=bundle,
        owner_user_id="alice",
        organization_id="org-acme",
    )

    assert summary["emails"]["imported"] == 2
    assert summary["emails"]["skipped_duplicate"] == 0
    assert summary["ticket_tasks"]["imported"] == 2
    assert summary["ticket_tasks"]["skipped_duplicate"] == 0
    imported_by_mid = {
        email.message_id: email for email in destination.emails
    }
    assert set(imported_by_mid) == {"<old@example.com>", "<new@example.com>"}
    old_email = imported_by_mid["<old@example.com>"]
    assert old_email.thread_id == "<thread-a>"
    assert old_email.fingerprint == "fp-1"
    assert old_email.is_read is False
    linked_task = next(
        task
        for task in destination.tasks
        if task.related_email_id is not None
    )
    assert linked_task.task_uid == "taskuidaaaaaaaaaaaaaaaaaaaaaaaa01"
    assert linked_task.related_email_id == imported_by_mid["<new@example.com>"].id
    assert linked_task.related_thread_id == "<thread-a>"
    standalone_task = next(
        task for task in destination.tasks if task.related_email_id is None
    )
    assert standalone_task.source_type == "manual"


@pytest.mark.asyncio
async def test_reimport_same_bundle_reports_all_skipped_without_duplicates(
    seeded_session,
):
    bundle = await export_tenant_archive(
        seeded_session, owner_user_id="alice", organization_id="org-acme"
    )

    first_summary = await import_tenant_archive(
        seeded_session,
        bundle=bundle,
        owner_user_id="alice",
        organization_id="org-acme",
    )
    second_summary = await import_tenant_archive(
        seeded_session,
        bundle=bundle,
        owner_user_id="alice",
        organization_id="org-acme",
    )

    assert first_summary["emails"]["imported"] == 0
    assert first_summary["emails"]["skipped_duplicate"] == 2
    assert second_summary["emails"]["imported"] == 0
    assert second_summary["emails"]["skipped_duplicate"] == 2
    assert second_summary["ticket_tasks"]["imported"] == 0
    assert second_summary["ticket_tasks"]["skipped_duplicate"] == 2
    assert len(seeded_session.emails) == 2
    assert len(seeded_session.tasks) == 2


def build_valid_bundle() -> dict:
    """Handcraft a minimal schema-valid bundle for validation tests."""
    return {
        "manifest": {
            "archive_kind": ARCHIVE_KIND,
            "schema_version": CURRENT_ARCHIVE_SCHEMA_VERSION,
            "exported_at": "2026-07-11T08:00:00+00:00",
            "included_domains": ["emails", "ticket_tasks"],
            "excluded_domains": ["credentials"],
            "source_scope": {
                "owner_user_id": "alice",
                "organization_id": "org-acme",
                "organization_scope_label": "org-acme",
            },
            "counts": {"emails": 1, "ticket_tasks": 0},
        },
        "records": {
            "emails": [
                {
                    "message_id": "<clean@example.com>",
                    "thread_id": None,
                    "fingerprint": None,
                    "sender": "s@example.com",
                    "reply_to": None,
                    "recipients": "o@example.com",
                    "subject": "Clean",
                    "in_reply_to": None,
                    "references": None,
                    "date": "2026-07-10T09:00:00+00:00",
                    "body": "hello",
                    "is_read": True,
                    "attachments": [],
                }
            ],
            "ticket_tasks": [],
        },
    }


@pytest.mark.asyncio
async def test_import_rejects_unknown_newer_schema_version():
    bundle = build_valid_bundle()
    bundle["manifest"]["schema_version"] = (
        max(SUPPORTED_ARCHIVE_SCHEMA_VERSIONS) + 1
    )

    with pytest.raises(TenantArchiveSchemaUnsupported):
        await import_tenant_archive(
            MockArchiveSession(),
            bundle=bundle,
            owner_user_id="alice",
            organization_id="org-acme",
        )


@pytest.mark.asyncio
async def test_import_rejects_bundle_from_mismatched_organization():
    bundle = build_valid_bundle()
    bundle["manifest"]["source_scope"]["organization_id"] = "org-other"

    with pytest.raises(TenantArchiveScopeMismatch):
        await import_tenant_archive(
            MockArchiveSession(),
            bundle=bundle,
            owner_user_id="alice",
            organization_id="org-acme",
        )


@pytest.mark.parametrize(
    ("mutation",),
    [
        (lambda bundle: bundle.pop("manifest"),),
        (lambda bundle: bundle.pop("records"),),
        (lambda bundle: bundle["manifest"].__setitem__("archive_kind", "other"),),
        (
            lambda bundle: bundle["manifest"].__setitem__(
                "schema_version", "not-an-int"
            ),
        ),
        (lambda bundle: bundle["manifest"].pop("source_scope"),),
        (
            lambda bundle: bundle["records"].__setitem__("emails", "nope"),
        ),
        (
            lambda bundle: bundle["records"]["emails"][0].pop("message_id"),
        ),
        (
            lambda bundle: bundle["records"]["emails"][0].__setitem__(
                "date", "not-a-date"
            ),
        ),
        (
            lambda bundle: bundle["records"]["ticket_tasks"].append(
                {"task_uid": ""}
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_import_rejects_malformed_bundles(mutation):
    bundle = build_valid_bundle()
    mutation(bundle)

    with pytest.raises(TenantArchiveBundleInvalid):
        await import_tenant_archive(
            MockArchiveSession(),
            bundle=bundle,
            owner_user_id="alice",
            organization_id="org-acme",
        )


@pytest.mark.asyncio
async def test_import_rejects_angle_bracket_message_id_duplicates_before_writes():
    """Equivalent message-id spellings must not reach a unique constraint."""
    bundle = build_valid_bundle()
    duplicate = dict(bundle["records"]["emails"][0])
    duplicate["message_id"] = "clean@example.com"
    bundle["records"]["emails"].append(duplicate)
    destination = MockArchiveSession()

    with pytest.raises(TenantArchiveBundleInvalid):
        await import_tenant_archive(
            destination,
            bundle=bundle,
            owner_user_id="alice",
            organization_id="org-acme",
        )

    assert destination.emails == []
    assert destination.commit_count == 0


@pytest.mark.asyncio
async def test_import_rejects_duplicate_task_uids_before_writes():
    """Duplicate task identities must fail before email rows are staged."""
    bundle = build_valid_bundle()
    task = {
        "task_uid": "taskuidduplicate000000000000000001",
        "title": "Review report",
    }
    bundle["records"]["ticket_tasks"].extend([dict(task), dict(task)])
    destination = MockArchiveSession()

    with pytest.raises(TenantArchiveBundleInvalid):
        await import_tenant_archive(
            destination,
            bundle=bundle,
            owner_user_id="alice",
            organization_id="org-acme",
        )

    assert destination.emails == []
    assert destination.tasks == []
    assert destination.commit_count == 0


@pytest.mark.asyncio
async def test_import_sanitizes_email_attachment_and_task_display_text():
    """Archive display fields cannot persist active HTML or script markup."""
    bundle = build_valid_bundle()
    email = bundle["records"]["emails"][0]
    email.update(
        {
            "sender": '<img src=x onerror="alert(1)">sender@example.com',
            "recipients": '<b>owner@example.com</b>',
            "subject": '<b>Quarterly report</b>',
            "body": '<script>alert(1)</script><p>Read me</p>',
            "attachments": [{"filename": "<script>x</script>report.txt"}],
        }
    )
    bundle["records"]["ticket_tasks"].append(
        {
            "task_uid": "taskuidhtml0000000000000000000001",
            "title": "<strong>Review report</strong>",
        }
    )
    destination = MockArchiveSession()

    await import_tenant_archive(
        destination,
        bundle=bundle,
        owner_user_id="alice",
        organization_id="org-acme",
    )

    imported_email = destination.emails[0]
    assert imported_email.sender == "sender@example.com"
    assert imported_email.recipients == "owner@example.com"
    assert imported_email.subject == "Quarterly report"
    assert imported_email.body == "Read me"
    assert imported_email.attachments[0].filename == "report.txt"
    assert destination.tasks[0].title == "Review report"
