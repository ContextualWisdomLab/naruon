"""Tenant archive export/import for the email/thread/task domain (slice 1).

The archive contract:

- ``export_tenant_archive`` produces a deterministic, versioned JSON bundle
  scoped to exactly one owner user + organization. Record ordering is stable
  (emails by ``(date, id)``, ticket tasks by ``(created_at, id)``) so two
  exports of unchanged data differ only in the ``exported_at`` manifest stamp.
- The bundle carries opaque public identifiers only: email ``message_id`` /
  ``thread_id`` / ``fingerprint`` and ticket-task ``task_uid``. Sequential
  database primary keys are never exported; task-to-email links are preserved
  through the source ``message_id`` provenance instead of numeric ids.
- Credential-bearing surfaces (tenant mailbox credentials, LLM provider API
  keys, runner registration tokens) and derived vector payloads are excluded;
  attachments are listed as metadata references without binary content so
  later slices can extend the same bundle format with payload transfer.
- ``import_tenant_archive`` re-scopes every record to the importing session's
  owner + organization (taken from the signed session, never from the bundle)
  while preserving domain identifiers and provenance. Import is dedupe-safe:
  emails match on the owner-scoped unique message id (with the repo's strong
  fingerprint fallback) and tasks match on their globally unique ``task_uid``,
  so re-importing the same bundle reports every record as skipped instead of
  duplicating rows.
"""

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Attachment, Email, TicketTask
from services.embedding import STORAGE_EMBEDDING_DIMENSION

ARCHIVE_KIND = "naruon_tenant_archive"
CURRENT_ARCHIVE_SCHEMA_VERSION = 1
SUPPORTED_ARCHIVE_SCHEMA_VERSIONS = frozenset({CURRENT_ARCHIVE_SCHEMA_VERSION})
INCLUDED_DOMAINS = ("emails", "ticket_tasks")
EXCLUDED_DOMAINS = (
    "credentials",
    "llm_providers",
    "runner_tokens",
    "embeddings",
    "attachment_binary_content",
    "content_graph",
    "project_graph",
)
DEFAULT_ATTACHMENT_CONTENT_TYPE = "text/plain"
DEFAULT_PARSE_STATUS = "parsed"
DEFAULT_PARSER_KEY = "plain_text"


class TenantArchiveError(Exception):
    """Base class for tenant archive failures with a deterministic code."""

    error_code = "archive_error"
    public_message = "Tenant archive operation failed"


class TenantArchiveBundleInvalid(TenantArchiveError):
    """Raised when a bundle does not conform to the archive contract."""

    error_code = "archive_bundle_malformed"
    public_message = "Archive bundle does not match the expected structure"


class TenantArchiveSchemaUnsupported(TenantArchiveError):
    """Raised when a bundle uses an unknown or newer schema version."""

    error_code = "archive_schema_unsupported"
    public_message = (
        "Archive schema version is unknown to this deployment; upgrade before "
        "importing this bundle"
    )


class TenantArchiveScopeMismatch(TenantArchiveError):
    """Raised when a bundle was exported from a different organization."""

    error_code = "archive_scope_mismatch"
    public_message = "Archive bundle belongs to a different organization scope"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _iso_utc(value: datetime.datetime) -> str:
    """Normalize a datetime to a timezone-aware UTC ISO-8601 string."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc).isoformat()
    return value.astimezone(datetime.timezone.utc).isoformat()


def _parse_bundle_datetime(value: object, field_name: str) -> datetime.datetime:
    """Parse an ISO-8601 bundle timestamp, failing closed on bad input."""
    if isinstance(value, datetime.datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        try:
            moment = datetime.datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise TenantArchiveBundleInvalid(
                f"Bundle field '{field_name}' is not a valid ISO-8601 timestamp"
            ) from exc
    else:
        raise TenantArchiveBundleInvalid(
            f"Bundle field '{field_name}' must be an ISO-8601 timestamp"
        )
    if moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment.astimezone(datetime.timezone.utc)


def _require_bundle_str(record: object, key: str) -> str:
    """Require a non-empty string field on a bundle record."""
    if not isinstance(record, dict):
        raise TenantArchiveBundleInvalid("Bundle records must be JSON objects")
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TenantArchiveBundleInvalid(
            f"Bundle record field '{key}' must be a non-empty string"
        )
    return value


def _optional_bundle_str(record: dict, key: str) -> str | None:
    """Return an optional trimmed string field from a bundle record."""
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TenantArchiveBundleInvalid(
            f"Bundle record field '{key}' must be a string when present"
        )
    return value.strip() or None


def _optional_bundle_bool(record: dict, key: str, default: bool) -> bool:
    """Return an optional boolean field from a bundle record."""
    value = record.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise TenantArchiveBundleInvalid(
            f"Bundle record field '{key}' must be a boolean when present"
        )
    return value


def _attachment_reference(message_id: str, ordinal_index: int) -> str:
    """Build the deterministic attachment reference for later slices."""
    return f"{message_id}#attachment-{ordinal_index}"


def _email_record(email: Email) -> dict:
    """Serialize one eager-loaded email row into its bundle record."""
    ordered_attachments = sorted(
        email.attachments,
        key=lambda item: (item.filename, item.content_type, item.id),
    )
    attachments = [
        {
            "attachment_ref": _attachment_reference(email.message_id, ordinal),
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "parse_status": attachment.parse_status,
            "parse_content_type": attachment.parse_content_type,
            "parser_key": attachment.parser_key,
            "parse_error_code": attachment.parse_error_code,
        }
        for ordinal, attachment in enumerate(ordered_attachments, start=1)
    ]
    return {
        "message_id": email.message_id,
        "thread_id": email.thread_id,
        "fingerprint": email.fingerprint,
        "sender": email.sender,
        "reply_to": email.reply_to,
        "recipients": email.recipients,
        "subject": email.subject,
        "in_reply_to": email.in_reply_to,
        "references": email.references,
        "date": _iso_utc(email.date),
        "body": email.body,
        "is_read": email.is_read,
        "attachments": attachments,
    }


def _task_record(
    task: TicketTask, message_id_by_email_id: dict[int, str]
) -> dict:
    """Serialize one ticket task row, mapping its email link to message id."""
    related_email_id = task.related_email_id
    return {
        "task_uid": task.task_uid,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "source_type": task.source_type,
        "related_message_id": (
            message_id_by_email_id.get(related_email_id)
            if related_email_id is not None
            else None
        ),
        "related_thread_id": task.related_thread_id,
        "created_at": (
            _iso_utc(task.created_at) if task.created_at is not None else None
        ),
        "updated_at": (
            _iso_utc(task.updated_at) if task.updated_at is not None else None
        ),
    }


async def export_tenant_archive(
    session: AsyncSession,
    *,
    owner_user_id: str,
    organization_id: str,
) -> dict:
    """Export the owner-scoped email/thread/task domain as a versioned bundle.

    Read-only; never touches credential-bearing tables and never includes
    embedding vectors or attachment binary content.
    """
    email_result = await session.execute(
        select(Email)
        .where(*Email.owner_filters(owner_user_id, organization_id))
        .options(selectinload(Email.attachments))
        .order_by(Email.date, Email.id)
    )
    emails = sorted(
        email_result.scalars().all(),
        key=lambda email: (email.date, email.id if email.id is not None else -1),
    )
    task_result = await session.execute(
        select(TicketTask)
        .where(
            TicketTask.user_id == owner_user_id,
            TicketTask.organization_id == organization_id,
        )
        .order_by(TicketTask.created_at, TicketTask.id)
    )
    tasks = sorted(
        task_result.scalars().all(),
        key=lambda task: (
            task.created_at or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
            task.id if task.id is not None else -1,
        ),
    )

    message_id_by_email_id = {
        email.id: email.message_id for email in emails if email.id is not None
    }
    email_records = [_email_record(email) for email in emails]
    task_records = [
        _task_record(task, message_id_by_email_id) for task in tasks
    ]
    attachment_reference_count = sum(
        len(record["attachments"]) for record in email_records
    )

    return {
        "manifest": {
            "archive_kind": ARCHIVE_KIND,
            "schema_version": CURRENT_ARCHIVE_SCHEMA_VERSION,
            "exported_at": _utc_now_iso(),
            "included_domains": list(INCLUDED_DOMAINS),
            "excluded_domains": list(EXCLUDED_DOMAINS),
            "source_scope": {
                "owner_user_id": owner_user_id,
                "organization_id": organization_id,
                "organization_scope_label": organization_id,
            },
            "counts": {
                "emails": len(email_records),
                "ticket_tasks": len(task_records),
                "attachment_references": attachment_reference_count,
            },
        },
        "records": {"emails": email_records, "ticket_tasks": task_records},
    }


def _validate_attachment_record(record: object) -> dict:
    """Validate and normalize one attachment metadata entry."""
    filename = _require_bundle_str(record, "filename")
    source = record if isinstance(record, dict) else {}

    def optional_str(key: str) -> str | None:
        value = source.get(key)
        if value is None or isinstance(value, str):
            return value
        raise TenantArchiveBundleInvalid(
            f"Bundle attachment field '{key}' must be a string when present"
        )

    content_type = optional_str("content_type") or DEFAULT_ATTACHMENT_CONTENT_TYPE
    parse_status = optional_str("parse_status") or DEFAULT_PARSE_STATUS
    parse_content_type = (
        optional_str("parse_content_type") or DEFAULT_ATTACHMENT_CONTENT_TYPE
    )
    parser_key = optional_str("parser_key") or DEFAULT_PARSER_KEY
    return {
        "filename": filename,
        "content_type": content_type,
        "parse_status": parse_status,
        "parse_content_type": parse_content_type,
        "parser_key": parser_key,
        "parse_error_code": optional_str("parse_error_code"),
    }


def _validate_email_record(record: object) -> dict:
    """Validate and normalize one email bundle record."""
    message_id = _require_bundle_str(record, "message_id")
    source = record if isinstance(record, dict) else {}
    sender = _require_bundle_str(record, "sender")
    body_value = source.get("body")
    if not isinstance(body_value, str):
        raise TenantArchiveBundleInvalid(
            "Bundle email record field 'body' must be a string"
        )
    raw_attachments = source.get("attachments", [])
    if not isinstance(raw_attachments, list):
        raise TenantArchiveBundleInvalid(
            "Bundle email record field 'attachments' must be a list"
        )
    return {
        "message_id": message_id,
        "thread_id": _optional_bundle_str(source, "thread_id"),
        "fingerprint": _optional_bundle_str(source, "fingerprint"),
        "sender": sender,
        "reply_to": _optional_bundle_str(source, "reply_to"),
        "recipients": _optional_bundle_str(source, "recipients"),
        "subject": _optional_bundle_str(source, "subject"),
        "in_reply_to": _optional_bundle_str(source, "in_reply_to"),
        "references": _optional_bundle_str(source, "references"),
        "date": _parse_bundle_datetime(source.get("date"), "date"),
        "body": body_value,
        "is_read": _optional_bundle_bool(source, "is_read", True),
        "attachments": [
            _validate_attachment_record(entry) for entry in raw_attachments
        ],
    }


def _validate_task_record(record: object) -> dict:
    """Validate and normalize one ticket-task bundle record."""
    task_uid = _require_bundle_str(record, "task_uid")
    title = _require_bundle_str(record, "title")
    source = record if isinstance(record, dict) else {}
    status = _optional_bundle_str(source, "status") or "open"
    priority = _optional_bundle_str(source, "priority") or "normal"
    source_type = _optional_bundle_str(source, "source_type") or "email"
    created_at_value = source.get("created_at")
    updated_at_value = source.get("updated_at")
    return {
        "task_uid": task_uid,
        "title": title,
        "status": status,
        "priority": priority,
        "source_type": source_type,
        "related_message_id": _optional_bundle_str(
            source, "related_message_id"
        ),
        "related_thread_id": _optional_bundle_str(source, "related_thread_id"),
        "created_at": (
            _parse_bundle_datetime(created_at_value, "created_at")
            if created_at_value is not None
            else datetime.datetime.now(datetime.timezone.utc)
        ),
        "updated_at": (
            _parse_bundle_datetime(updated_at_value, "updated_at")
            if updated_at_value is not None
            else datetime.datetime.now(datetime.timezone.utc)
        ),
    }


def _validated_bundle(
    bundle: object, expected_organization_id: str
) -> tuple[list[dict], list[dict]]:
    """Validate the bundle envelope and records against the slice-1 contract."""
    if not isinstance(bundle, dict):
        raise TenantArchiveBundleInvalid("Bundle must be a JSON object")
    manifest = bundle.get("manifest")
    records = bundle.get("records")
    if not isinstance(manifest, dict):
        raise TenantArchiveBundleInvalid("Bundle manifest must be an object")
    if not isinstance(records, dict):
        raise TenantArchiveBundleInvalid("Bundle records must be an object")
    if manifest.get("archive_kind") != ARCHIVE_KIND:
        raise TenantArchiveBundleInvalid(
            "Bundle manifest archive_kind does not identify a Naruon archive"
        )
    schema_version = manifest.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise TenantArchiveBundleInvalid(
            "Bundle manifest schema_version must be an integer"
        )
    if schema_version not in SUPPORTED_ARCHIVE_SCHEMA_VERSIONS:
        raise TenantArchiveSchemaUnsupported()
    source_scope = manifest.get("source_scope")
    if not isinstance(source_scope, dict):
        raise TenantArchiveBundleInvalid(
            "Bundle manifest source_scope must be an object"
        )
    if source_scope.get("organization_id") != expected_organization_id:
        raise TenantArchiveScopeMismatch()
    raw_emails = records.get("emails")
    raw_tasks = records.get("ticket_tasks")
    if not isinstance(raw_emails, list) or not isinstance(raw_tasks, list):
        raise TenantArchiveBundleInvalid(
            "Bundle records must contain 'emails' and 'ticket_tasks' lists"
        )
    return (
        [_validate_email_record(entry) for entry in raw_emails],
        [_validate_task_record(entry) for entry in raw_tasks],
    )


async def _find_existing_email(
    session: AsyncSession,
    *,
    owner_user_id: str,
    organization_id: str,
    message_id: str,
    fingerprint: str | None,
) -> Email | None:
    """Find an existing owner-scoped duplicate by message id or fingerprint."""
    message_lookup_values = {message_id, f"<{message_id}>"}
    duplicate_predicate = Email.message_id.in_(message_lookup_values)
    if fingerprint:
        duplicate_predicate = duplicate_predicate | (Email.fingerprint == fingerprint)
    result = await session.execute(
        select(Email)
        .where(
            *Email.owner_filters(owner_user_id, organization_id),
            duplicate_predicate,
        )
        .order_by(Email.id)
    )
    return result.scalars().first()


async def _find_existing_task(
    session: AsyncSession,
    *,
    owner_user_id: str,
    organization_id: str,
    task_uid: str,
) -> TicketTask | None:
    """Find an existing owner-scoped task by its opaque public uid."""
    result = await session.execute(
        select(TicketTask).where(
            TicketTask.user_id == owner_user_id,
            TicketTask.organization_id == organization_id,
            TicketTask.task_uid == task_uid,
        )
    )
    return result.scalar_one_or_none()


def _zero_embedding() -> list[float]:
    """Zero vector placeholder; embeddings are regenerated in later slices."""
    return [0.0] * STORAGE_EMBEDDING_DIMENSION


def _staged_email_from_record(
    record: dict, *, owner_user_id: str, organization_id: str
) -> Email:
    """Build an unflushed Email row (plus attachment metadata) from a record."""
    email_obj = Email(
        user_id=owner_user_id,
        organization_id=organization_id,
        message_id=record["message_id"],
        thread_id=record["thread_id"],
        fingerprint=record["fingerprint"],
        sender=record["sender"],
        reply_to=record["reply_to"],
        recipients=record["recipients"],
        subject=record["subject"],
        in_reply_to=record["in_reply_to"],
        references=record["references"],
        date=record["date"],
        body=record["body"],
        is_read=record["is_read"],
        embedding=_zero_embedding(),
    )
    for attachment in record["attachments"]:
        email_obj.attachments.append(
            Attachment(
                filename=attachment["filename"],
                # Slice 1 is metadata-only; binary payloads arrive in a later
                # slice keyed by the bundle attachment_ref.
                content="",
                content_type=attachment["content_type"],
                parse_status=attachment["parse_status"],
                parse_content_type=attachment["parse_content_type"],
                parser_key=attachment["parser_key"],
                parse_error_code=attachment["parse_error_code"],
            )
        )
    return email_obj


async def import_tenant_archive(
    session: AsyncSession,
    *,
    bundle: object,
    owner_user_id: str,
    organization_id: str,
) -> dict:
    """Import a validated bundle into the session owner's scope, dedupe-safe.

    Records are re-scoped to ``owner_user_id`` / ``organization_id`` (the
    signed-session destination scope) while preserving opaque public ids and
    source provenance. Re-importing the same bundle skips every record.
    """
    email_records, task_records = _validated_bundle(bundle, organization_id)

    imported_email_ids_by_message_id: dict[str, int] = {}
    emails_imported = 0
    emails_skipped = 0
    staged_emails: list[Email] = []
    for record in email_records:
        existing_email = await _find_existing_email(
            session,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            message_id=record["message_id"],
            fingerprint=record["fingerprint"],
        )
        if existing_email is not None and existing_email.id is not None:
            imported_email_ids_by_message_id[record["message_id"]] = existing_email.id
            imported_email_ids_by_message_id[existing_email.message_id] = (
                existing_email.id
            )
            emails_skipped += 1
            continue
        staged_emails.append(
            _staged_email_from_record(
                record,
                owner_user_id=owner_user_id,
                organization_id=organization_id,
            )
        )
    if staged_emails:
        session.add_all(staged_emails)
        await session.flush()
    for staged_email in staged_emails:
        if staged_email.id is not None:
            imported_email_ids_by_message_id[staged_email.message_id] = (
                staged_email.id
            )
            emails_imported += 1

    tasks_imported = 0
    tasks_skipped = 0
    staged_tasks: list[TicketTask] = []
    for record in task_records:
        existing_task = await _find_existing_task(
            session,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            task_uid=record["task_uid"],
        )
        if existing_task is not None:
            tasks_skipped += 1
            continue
        related_message_id = record["related_message_id"]
        related_email_id = (
            imported_email_ids_by_message_id.get(related_message_id)
            if related_message_id is not None
            else None
        )
        if related_message_id is not None and related_email_id is None:
            existing_related_email = await _find_existing_email(
                session,
                owner_user_id=owner_user_id,
                organization_id=organization_id,
                message_id=related_message_id,
                fingerprint=None,
            )
            if existing_related_email is not None:
                related_email_id = existing_related_email.id
        staged_tasks.append(
            TicketTask(
                task_uid=record["task_uid"],
                user_id=owner_user_id,
                organization_id=organization_id,
                title=record["title"],
                status=record["status"],
                priority=record["priority"],
                source_type=record["source_type"],
                related_email_id=related_email_id,
                related_thread_id=record["related_thread_id"],
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
        )
    if staged_tasks:
        session.add_all(staged_tasks)
        tasks_imported = len(staged_tasks)

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    attachment_reference_count = sum(
        len(record["attachments"]) for record in email_records
    )
    return {
        "archive_schema_version": CURRENT_ARCHIVE_SCHEMA_VERSION,
        "emails": {
            "imported": emails_imported,
            "skipped_duplicate": emails_skipped,
        },
        "ticket_tasks": {
            "imported": tasks_imported,
            "skipped_duplicate": tasks_skipped,
        },
        "attachment_references": attachment_reference_count,
    }
